"""Integration tests for the multi-device HTTP broker transport."""

import tempfile
import threading
import time
import unittest
from pathlib import Path

from broker.broker import Broker
from broker.server import BrokerServer
from clients.http_broker import HttpBroker
from clients.publisher import ACKED, QUEUED, SOURCE_OPERATOR, Publisher
from clients.subscriber import STATUS_RECEIVED, Subscriber


class HttpBrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        broker = Broker(db_path=str(Path(self.temp_dir.name) / "http.db"), delivery_delay=0)
        self.server = BrokerServer(broker=broker, host="127.0.0.1", port=0)
        self.server_thread = threading.Thread(target=self.server.run, daemon=True)
        self.server_thread.start()
        deadline = time.time() + 2
        while self.server._server is None and time.time() < deadline:
            time.sleep(0.01)
        self.assertIsNotNone(self.server._server, "broker server did not start")
        self.client = HttpBroker(f"http://127.0.0.1:{self.server._server.server_port}")

    def tearDown(self):
        self.server.shutdown()
        self.server_thread.join(timeout=2)
        self.temp_dir.cleanup()

    def test_remote_publish_poll_ack_status_and_offline_queue(self):
        subscriber = Subscriber(
            "fire_station", "Fire Station", ["emergency/fire"], self.client
        )
        subscriber.connect()
        publisher = Publisher(SOURCE_OPERATOR, self.client)

        first = publisher.send("FIRE", "Jaro", "HIGH")
        subscriber.refresh_reports()
        self.assertIn(first.report_id, subscriber.reports)
        self.assertEqual(
            [report.report_id for report in subscriber.drain_new_reports()],
            [first.report_id],
        )
        self.assertTrue(subscriber.set_status(first.report_id, STATUS_RECEIVED))

        deadline = time.time() + 2
        while time.time() < deadline:
            publisher.refresh_receipts()
            if first.receipts.get("Fire Station") == ACKED:
                break
            time.sleep(0.02)
        self.assertEqual(first.receipts.get("Fire Station"), ACKED)

        subscriber.disconnect()
        queued = publisher.send("FIRE", "Molo", "MEDIUM")
        self.assertEqual(queued.receipts.get("Fire Station"), QUEUED)
        subscriber.connect()
        subscriber.refresh_reports()
        self.assertIn(queued.report_id, subscriber.reports)
        subscriber.disconnect()


if __name__ == "__main__":
    unittest.main()
