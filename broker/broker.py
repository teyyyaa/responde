from __future__ import annotations

import threading
from typing import Callable

from broker.storage import StorageManager


class Broker:
    """Persistent broker compatible with the Publisher and Subscriber clients."""

    def __init__(self, db_path: str = "database/responde.db", delivery_delay: float = 0.1, max_retries: int = 5):
        self.delivery_delay = delivery_delay
        self.storage = StorageManager(db_path, max_retries=max_retries)
        self.subscribers: dict[str, dict] = {}
        self.log: list[tuple] = []
        self.statuses: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()
        self._in_flight: set[tuple[str, str]] = set()

    def register_subscriber(self, subscriber_id: str, name: str, topics: list[str], callback: Callable):
        with self._lock:
            self.subscribers[subscriber_id] = {
                "name": name,
                "topics": list(topics),
                "callback": callback,
                "online": False,
            }
        self.storage.register_subscriber(subscriber_id, name, topics, is_online=False)

    def subscribe(self, subscriber):
        """Compatibility alias for the original broker API."""
        callback = getattr(subscriber, "_on_message", None)
        if callback is not None:
            subscriber_id = getattr(subscriber, "subscriber_id", getattr(subscriber, "name", "subscriber"))
            self.register_subscriber(subscriber_id, getattr(subscriber, "name", subscriber_id),
                                     list(getattr(subscriber, "topics", [])), callback)
        return None

    def set_online(self, subscriber_id: str, online: bool):
        with self._lock:
            sub = self.subscribers.get(subscriber_id)
            if sub is not None:
                sub["online"] = online
        self.storage.set_subscriber_status(subscriber_id, online)
        if online:
            self._deliver_pending(subscriber_id)

    def publish(self, topic: str, report: dict):
        report_id = str(report["report_id"])
        category = str(topic)
        self.storage.enqueue_report(report_id, category, report)

        delivered, queued = [], []
        with self._lock:
            targets = [
                (sid, sub) for sid, sub in self.subscribers.items()
                if "*" in sub["topics"] or topic in sub["topics"]
            ]
        for subscriber_id, sub in targets:
            if sub["online"]:
                delivered.append(sub["name"])
                self._deliver_later(subscriber_id, topic, report)
            else:
                queued.append(sub["name"])
        return delivered, queued

    def poll(self, subscriber_id: str) -> list[dict]:
        return self.storage.get_pending_deliveries(subscriber_id)

    def get_subscriber_reports(self, subscriber_id: str) -> list[dict]:
        return self.storage.get_subscriber_reports(subscriber_id)

    def get_publisher_reports(self, source: str) -> list[dict]:
        return self.storage.get_publisher_reports(source)

    def _deliver_pending(self, subscriber_id: str):
        with self._lock:
            sub = self.subscribers.get(subscriber_id)
            if sub is None or not sub["online"]:
                return
        for item in self.storage.get_pending_deliveries(subscriber_id):
            report = item["payload"]
            self._deliver_later(subscriber_id, item["category"], report)

    def _deliver_later(self, subscriber_id: str, topic: str, report: dict):
        key = (subscriber_id, str(report["report_id"]))
        with self._lock:
            if key in self._in_flight:
                return
            self._in_flight.add(key)
        timer = threading.Timer(self.delivery_delay, self._deliver,
                                (subscriber_id, topic, report))
        timer.daemon = True
        timer.start()

    def _deliver(self, subscriber_id: str, topic: str, report: dict):
        key = (subscriber_id, str(report["report_id"]))
        with self._lock:
            sub = self.subscribers.get(subscriber_id)
            if sub is None or not sub["online"]:
                self._in_flight.discard(key)
                return
            callback = sub["callback"]
        try:
            result = callback(topic, report)
            if result is False:
                self.nack(subscriber_id, str(report["report_id"]), "Subscriber rejected delivery")
            else:
                self.ack(subscriber_id, str(report["report_id"]))
        except Exception as exc:
            self.nack(subscriber_id, str(report["report_id"]), str(exc))
        finally:
            with self._lock:
                self._in_flight.discard(key)

    def ack(self, subscriber_id: str, report_id: str):
        found = self.storage.ack_by_report(subscriber_id, str(report_id))
        if found:
            self.log.append(("ACK", subscriber_id, str(report_id)))
        return found

    def nack(self, subscriber_id: str, report_id: str, reason: str = "Delivery failed"):
        status = self.storage.nack_by_report(subscriber_id, str(report_id), reason)
        self.log.append(("NACK", subscriber_id, str(report_id), status))
        return status

    def update_status(self, subscriber_id: str, report_id: str, status: str):
        updated = self.storage.update_status(subscriber_id, str(report_id), status)
        if not updated:
            raise ValueError("Unknown report")
        key = (subscriber_id, str(report_id))
        self.statuses[key] = status
        self.log.append(("STATUS", subscriber_id, str(report_id), status))
        return status

    def expiry_reaper(self, interval_seconds: float = 0.0):
        """Redeliver pending work to currently online subscribers."""
        for subscriber_id, sub in list(self.subscribers.items()):
            if sub["online"]:
                self._deliver_pending(subscriber_id)
        if interval_seconds > 0:
            timer = threading.Timer(interval_seconds, self.expiry_reaper, (interval_seconds,))
            timer.daemon = True
            timer.start()