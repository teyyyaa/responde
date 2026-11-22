"""Persistence and redelivery tests for the broker."""

import tempfile
import time
import unittest
from pathlib import Path

from broker.broker import Broker
from clients.messages import make_report
from clients.subscriber import Subscriber


class RedeliveryTests(unittest.TestCase):
    def test_offline_queue_survives_reconnect(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            db_path = str(Path(directory) / "redelivery.db")
            broker = Broker(db_path=db_path, delivery_delay=0.01)
            ambul = Subscriber("amb", "Ambulance", ["emergency/medical"], broker)
            ambul.connect()
            ambul.disconnect()

            report = make_report("MEDICAL", "Molo", "CRITICAL")
            broker.publish("emergency/medical", report)
            time.sleep(0.05)
            self.assertNotIn(report["report_id"], ambul.reports)

            ambul.connect()
            time.sleep(0.05)
            self.assertIn(report["report_id"], ambul.reports)

            broker2 = Broker(db_path=db_path, delivery_delay=0.01)
            persisted = broker2.storage.get_reports()
            self.assertTrue(any(row["report_uid"] == report["report_id"] for row in persisted))


if __name__ == "__main__":
    unittest.main()