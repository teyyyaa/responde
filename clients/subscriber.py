"""
Subscriber client shared by all responder dashboards.

Expected broker interface:
    register_subscriber(subscriber_id, name, topics, callback)
    set_online(subscriber_id, online)        # on True, redeliver queued reports
    ack(subscriber_id, report_id)
    nack(subscriber_id, report_id)
    update_status(subscriber_id, report_id, status)

The broker delivers a report by calling callback(topic, report_dict).
Report format: see clients/messages.py.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime

from clients.messages import validate_report

STATUS_NEW = "NEW"
STATUS_RECEIVED = "RECEIVED"
STATUS_RESPONDING = "RESPONDING"
STATUS_COMPLETED = "COMPLETED"
STATUS_ORDER = [STATUS_NEW, STATUS_RECEIVED, STATUS_RESPONDING, STATUS_COMPLETED]


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class ReceivedReport:
    report_id: str
    topic: str
    incident_type: str
    location: str
    severity: str
    description: str = ""
    source: str = ""
    sent_at: str = ""
    received_at: str = field(default_factory=now_str)
    status: str = STATUS_NEW
    status_history: list = field(default_factory=list)  # [(time, status)]

    @classmethod
    def from_message(cls, topic: str, msg: dict) -> "ReceivedReport":
        return cls(
            report_id=str(msg["report_id"]),
            topic=topic,
            incident_type=str(msg["incident_type"]).upper(),
            location=str(msg["location"]),
            severity=str(msg["severity"]).upper(),
            description=str(msg.get("description", "")),
            source=str(msg.get("source", "")),
            sent_at=str(msg.get("timestamp", "")),
        )


@dataclass
class HistoryEvent:
    time: str
    event: str
    report_id: str
    detail: str

    def __str__(self) -> str:
        rid = f" [{self.report_id}]" if self.report_id else ""
        return f"{self.time}  {self.event:<12}{rid} {self.detail}"


class Subscriber:
    def __init__(self, subscriber_id: str, name: str, topics: list[str], broker):
        self.subscriber_id = subscriber_id
        self.name = name
        self.topics = list(topics)
        self.broker = broker

        self.connected = False
        self._registered = False
        self._lock = threading.Lock()

        self.reports: dict[str, ReceivedReport] = {}
        self.history: list[HistoryEvent] = []

        # The broker may call us from another thread; the UI reads these queues.
        self.new_reports: "queue.Queue[ReceivedReport]" = queue.Queue()
        self.new_events: "queue.Queue[HistoryEvent]" = queue.Queue()

    # Connection
    def connect(self) -> None:
        if not self._registered:
            self.broker.register_subscriber(
                self.subscriber_id, self.name, self.topics, self._on_message
            )
            self._registered = True
            self._log("REGISTERED", "", f"topics: {', '.join(self.topics)}")
        self._restore_reports()
        self.connected = True
        self._log("CONNECTED", "", "online - waiting for reports")
        self.broker.set_online(self.subscriber_id, True)

    def _restore_reports(self) -> None:
        self.refresh_reports()

    def refresh_reports(self) -> list[ReceivedReport]:
        load_reports = getattr(self.broker, "get_subscriber_reports", None)
        if load_reports is None:
            return []

        changed = []
        for item in load_reports(self.subscriber_id):
            report_id = str(item["report_uid"])
            status = item["response_status"] or STATUS_NEW
            if status not in STATUS_ORDER:
                raise ValueError(f"Invalid persisted response status: {status}")
            report = self.reports.get(report_id)
            if report is None:
                report = ReceivedReport.from_message(item["category"], item["payload"])
                self.reports[report_id] = report
                self.new_reports.put(report)
                event_time = report.received_at
            elif report.status != status:
                changed.append(report)
                event_time = now_str()
            else:
                continue
            report.status = status
            report.status_history.append((event_time, status))
        return changed

    def disconnect(self) -> None:
        self.connected = False
        self.broker.set_online(self.subscriber_id, False)
        self._log("DISCONNECTED", "", "offline - broker will queue reports")

    # Receiving
    def _on_message(self, topic: str, msg: dict) -> bool:
        """Returns True on ACK, False on NACK."""
        report_id = str(msg.get("report_id", "?")) if isinstance(msg, dict) else "?"

        if not self.connected:
            self._send_nack(report_id, "received while offline")
            return False

        problem = validate_report(msg)
        if problem:
            self._send_nack(report_id, problem)
            return False

        with self._lock:
            duplicate = report_id in self.reports
            if not duplicate:
                report = ReceivedReport.from_message(topic, msg)
                report.status_history.append((report.received_at, STATUS_NEW))
                self.reports[report_id] = report

        if duplicate:
            # ACK again so the broker stops resending, but don't show it twice.
            self._log("DUPLICATE", report_id, "already received - ignored")
            self._send_ack(report_id)
            return True

        self._log("DELIVERED", report_id,
                  f"{report.incident_type} at {report.location} ({report.severity})")
        self._send_ack(report_id)
        self.new_reports.put(report)
        return True

    def _send_ack(self, report_id: str) -> None:
        try:
            self.broker.ack(self.subscriber_id, report_id)
            self._log("ACK", report_id, "delivery confirmed to broker")
        except Exception as exc:
            self._log("ACK FAILED", report_id, str(exc))

    def _send_nack(self, report_id: str, reason: str) -> None:
        try:
            self.broker.nack(self.subscriber_id, report_id)
        except Exception:
            pass
        self._log("NACK", report_id, reason)

    # Status updates (forward only)
    def can_set_status(self, report_id: str, status: str) -> bool:
        report = self.reports.get(report_id)
        if report is None or status not in STATUS_ORDER:
            return False
        return STATUS_ORDER.index(status) > STATUS_ORDER.index(report.status)

    def set_status(self, report_id: str, status: str) -> bool:
        if not self.can_set_status(report_id, status):
            return False
        report = self.reports[report_id]
        try:
            self.broker.update_status(self.subscriber_id, report_id, status)
        except Exception as exc:
            self._log("STATUS FAILED", report_id, f"{status}: {exc}")
            return False
        old = report.status
        report.status = status
        report.status_history.append((now_str(), status))
        self._log("STATUS", report_id, f"{old} -> {status}")
        return True

    # Helpers for the UI
    def drain_new_reports(self) -> list[ReceivedReport]:
        return self._drain(self.new_reports)

    def drain_new_events(self) -> list[HistoryEvent]:
        return self._drain(self.new_events)

    @staticmethod
    def _drain(q: queue.Queue) -> list:
        items = []
        while True:
            try:
                items.append(q.get_nowait())
            except queue.Empty:
                return items

    def _log(self, event: str, report_id: str, detail: str) -> None:
        entry = HistoryEvent(now_str(), event, report_id, detail)
        with self._lock:
            self.history.append(entry)
        self.new_events.put(entry)