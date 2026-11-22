import json
import sqlite3
from pathlib import Path
from typing import Any


class StorageManager:
    def __init__(self, db_path: str = "database/responde.db", max_retries: int = 5) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_uid TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                );

                CREATE TABLE IF NOT EXISTS subscribers (
                    subscriber_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    topics_json TEXT NOT NULL DEFAULT '[]',
                    is_online INTEGER NOT NULL DEFAULT 0,
                    last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                );

                CREATE TABLE IF NOT EXISTS delivery_queue (
                    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                    subscriber_id TEXT NOT NULL REFERENCES subscribers(subscriber_id) ON DELETE CASCADE,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'NACKED_RETRY', 'DELIVERED_ACKED', 'DEAD_LETTER')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    UNIQUE (report_id, subscriber_id)
                );

                CREATE INDEX IF NOT EXISTS idx_delivery_sub_status
                    ON delivery_queue (subscriber_id, status, queue_id);

                CREATE TABLE IF NOT EXISTS response_status (
                    subscriber_id TEXT NOT NULL REFERENCES subscribers(subscriber_id) ON DELETE CASCADE,
                    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    PRIMARY KEY (subscriber_id, report_id)
                );
                """
            )

    def register_subscriber(
        self, subscriber_id: str, display_name: str, topics: list[str], is_online: bool = True
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO subscribers (subscriber_id, display_name, topics_json, is_online, last_seen_at)
                VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                ON CONFLICT(subscriber_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    topics_json = excluded.topics_json,
                    is_online = excluded.is_online,
                    last_seen_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now');
                """,
                (subscriber_id, display_name, json.dumps(topics), int(is_online)),
            )

    def set_subscriber_status(self, subscriber_id: str, is_online: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE subscribers
                SET is_online = ?, last_seen_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE subscriber_id = ?;
                """,
                (int(is_online), subscriber_id),
            )

    def enqueue_report(self, report_uid: str, category: str, payload: dict[str, Any]) -> int:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reports (report_uid, category, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(report_uid) DO NOTHING;
                """,
                (report_uid, category, json.dumps(payload)),
            )
            row = conn.execute(
                "SELECT id FROM reports WHERE report_uid = ?;", (report_uid,)
            ).fetchone()
            if row is None:
                raise RuntimeError(f"Failed to retrieve persisted report {report_uid}")
            report_id = int(row["id"])

            subs = conn.execute("SELECT subscriber_id, topics_json FROM subscribers;").fetchall()
            for sub in subs:
                topics = json.loads(sub["topics_json"])
                if not topics or category in topics or "*" in topics:
                    conn.execute(
                        """
                        INSERT INTO delivery_queue (report_id, subscriber_id, status)
                        VALUES (?, ?, 'PENDING')
                        ON CONFLICT(report_id, subscriber_id) DO NOTHING;
                        """,
                        (report_id, sub["subscriber_id"]),
                    )
            return report_id

    def get_pending_deliveries(self, subscriber_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    dq.queue_id,
                    dq.report_id,
                    dq.subscriber_id,
                    dq.status,
                    dq.attempts,
                    r.report_uid,
                    r.category,
                    r.payload_json,
                    r.created_at
                FROM delivery_queue dq
                JOIN reports r ON r.id = dq.report_id
                WHERE dq.subscriber_id = ?
                  AND dq.status IN ('PENDING', 'NACKED_RETRY')
                ORDER BY dq.queue_id ASC;
                """,
                (subscriber_id,),
            ).fetchall()
            return [
                {
                    "queue_id": r["queue_id"],
                    "report_id": r["report_id"],
                    "report_uid": r["report_uid"],
                    "category": r["category"],
                    "payload": json.loads(r["payload_json"]),
                    "status": r["status"],
                    "attempts": r["attempts"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    def ack_delivery(self, queue_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE delivery_queue
                SET status = 'DELIVERED_ACKED',
                    attempts = attempts + 1,
                    last_error = NULL,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE queue_id = ?;
                """,
                (queue_id,),
            )

    def nack_delivery(self, queue_id: int, reason: str = "Delivery failed") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT attempts FROM delivery_queue WHERE queue_id = ?;", (queue_id,)
            ).fetchone()
            next_attempts = (int(row["attempts"]) if row else 0) + 1
            next_status = "DEAD_LETTER" if next_attempts >= self.max_retries else "NACKED_RETRY"
            conn.execute(
                """
                UPDATE delivery_queue
                SET status = ?,
                    attempts = ?,
                    last_error = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE queue_id = ?;
                """,
                (next_status, next_attempts, reason, queue_id),
            )
            return next_status

    def ack_by_report(self, subscriber_id: str, report_uid: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT dq.queue_id
                FROM delivery_queue dq
                JOIN reports r ON r.id = dq.report_id
                WHERE dq.subscriber_id = ? AND r.report_uid = ?;
                """,
                (subscriber_id, report_uid),
            ).fetchone()
            if row is None:
                return False
            queue_id = int(row["queue_id"])
        self.ack_delivery(queue_id)
        return True

    def nack_by_report(self, subscriber_id: str, report_uid: str, reason: str = "Delivery failed") -> str:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT dq.queue_id
                FROM delivery_queue dq
                JOIN reports r ON r.id = dq.report_id
                WHERE dq.subscriber_id = ? AND r.report_uid = ?;
                """,
                (subscriber_id, report_uid),
            ).fetchone()
            if row is None:
                return "NOT_FOUND"
            queue_id = int(row["queue_id"])
        return self.nack_delivery(queue_id, reason)

    def update_status(self, subscriber_id: str, report_uid: str, status: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM reports WHERE report_uid = ?;", (report_uid,)
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                """
                INSERT INTO response_status (subscriber_id, report_id, status)
                VALUES (?, ?, ?)
                ON CONFLICT(subscriber_id, report_id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now');
                """,
                (subscriber_id, int(row["id"]), status),
            )
            return True

    def get_reports(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.report_uid, r.category, r.payload_json, r.created_at,
                       dq.subscriber_id, dq.status, dq.attempts,
                       rs.status AS response_status
                FROM reports r
                LEFT JOIN delivery_queue dq ON dq.report_id = r.id
                LEFT JOIN response_status rs
                  ON rs.report_id = r.id AND rs.subscriber_id = dq.subscriber_id
                ORDER BY r.id ASC, dq.queue_id ASC;
                """
            ).fetchall()
            reports: dict[str, dict[str, Any]] = {}
            for row in rows:
                report = reports.setdefault(
                    row["report_uid"],
                    {
                        "report_uid": row["report_uid"],
                        "category": row["category"],
                        "payload": json.loads(row["payload_json"]),
                        "created_at": row["created_at"],
                        "deliveries": [],
                    },
                )
                if row["subscriber_id"]:
                    report["deliveries"].append(
                        {
                            "subscriber_id": row["subscriber_id"],
                            "status": row["status"],
                            "attempts": row["attempts"],
                            "response_status": row["response_status"],
                        }
                    )
            return list(reports.values())
