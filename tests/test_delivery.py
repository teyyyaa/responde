"""Delivery acknowledgment and response-status tests."""

import tempfile
import time
import unittest
from pathlib import Path

from broker.broker import Broker
from clients.messages import make_report
from clients.subscriber import (
    STATUS_COMPLETED,
    STATUS_RECEIVED,
    STATUS_RESPONDING,
    Subscriber,
)


class DeliveryTests(unittest.TestCase):
    def test_delivery_ack_and_response_status(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            broker = Broker(db_path=str(Path(directory) / "delivery.db"), delivery_delay=0.01)
            fire = Subscriber("fire", "Fire", ["emergency/fire"], broker)
            fire.connect()

            report = make_report("FIRE", "Lapaz", "MEDIUM")
            broker.publish("emergency/fire", report)
            time.sleep(0.05)

            report_id = report["report_id"]
            self.assertIn(report_id, fire.reports)
            self.assertTrue(("ACK", "fire", report_id) in broker.log)
            self.assertTrue(fire.set_status(report_id, STATUS_RECEIVED))
            self.assertTrue(fire.set_status(report_id, STATUS_RESPONDING))
            self.assertTrue(fire.set_status(report_id, STATUS_COMPLETED))
            self.assertEqual(broker.statuses[("fire", report_id)], STATUS_COMPLETED)


if __name__ == "__main__":
    unittest.main()
