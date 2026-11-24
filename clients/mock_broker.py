"""
In-memory stand-in for the real broker, used only for demos and tests.
Replace with broker/broker.py during integration.
"""

from __future__ import annotations

import threading
from collections import defaultdict


class MockBroker:
    def __init__(self, delivery_delay: float = 0.1):
        self.delivery_delay = delivery_delay
        self._lock = threading.Lock()
        self.subscribers = {}                   # id -> {name, topics, callback, online}
        self.offline_queue = defaultdict(list)  # id -> [(topic, report)]
        self.unacked = defaultdict(dict)        # id -> {report_id: (topic, report)}
        self.statuses = {}                      # (id, report_id) -> status
        self.log = []
        self._in_flight = set()

    # Subscriber side
    def register_subscriber(self, subscriber_id, name, topics, callback):
        with self._lock:
            self.subscribers[subscriber_id] = {
                "name": name, "topics": list(topics),
                "callback": callback, "online": False,
            }

    def set_online(self, subscriber_id, online):
        with self._lock:
            self.subscribers[subscriber_id]["online"] = online
            pending = []
            if online:
                pending = self.offline_queue.pop(subscriber_id, [])
        for topic, report in pending:
            self._deliver_later(subscriber_id, topic, report)

    def ack(self, subscriber_id, report_id):
        with self._lock:
            self.unacked[subscriber_id].pop(report_id, None)
        self.log.append(("ACK", subscriber_id, report_id))

    def nack(self, subscriber_id, report_id):
        with self._lock:
            item = self.unacked[subscriber_id].pop(report_id, None)
            if item:
                self.offline_queue[subscriber_id].append(item)
        self.log.append(("NACK", subscriber_id, report_id))

    def update_status(self, subscriber_id, report_id, status):
        with self._lock:
            self.statuses[(subscriber_id, report_id)] = status
        self.log.append(("STATUS", subscriber_id, report_id, status))

    # Publisher side
    def publish(self, topic, report):
        """Returns (delivered_names, queued_names)."""
        delivered, queued = [], []
        with self._lock:
            targets = [
                (sid, s) for sid, s in self.subscribers.items()
                if "*" in s["topics"] or topic in s["topics"]
            ]
            for sid, sub in targets:
                if sub["online"]:
                    delivered.append(sub["name"])
                else:
                    queued_report = (topic, report)
                    if queued_report not in self.offline_queue[sid]:
                        self.offline_queue[sid].append(queued_report)
                    queued.append(sub["name"])
        for sid, sub in targets:
            if sub["name"] in delivered:
                self._deliver_later(sid, topic, report)
        return delivered, queued

    # Internals
    def _deliver_later(self, subscriber_id, topic, report):
        key = (subscriber_id, str(report["report_id"]))
        with self._lock:
            if key in self._in_flight:
                return
            self._in_flight.add(key)
        t = threading.Timer(self.delivery_delay, self._deliver, (subscriber_id, topic, report))
        t.daemon = True
        t.start()

    def _deliver(self, subscriber_id, topic, report):
        key = (subscriber_id, str(report["report_id"]))
        with self._lock:
            sub = self.subscribers.get(subscriber_id)
            if sub is None:
                self._in_flight.discard(key)
                return
            if not sub["online"]:
                item = (topic, report)
                if item not in self.offline_queue[subscriber_id]:
                    self.offline_queue[subscriber_id].append(item)
                self._in_flight.discard(key)
                return
            self.unacked[subscriber_id][report["report_id"]] = (topic, report)
            callback = sub["callback"]
        try:
            callback(topic, report)
        finally:
            with self._lock:
                self._in_flight.discard(key)