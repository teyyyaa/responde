"""Persistence and redelivery tests for the broker."""

import tempfile
import time
import unittest
from pathlib import Path

from broker.broker import Broker
from clients.messages import make_report
from clients.subscriber import Subscriber


class RedeliveryTests(unittest.TestCase):
    def test_subscriber_restores_persisted_reports_and_status(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            db_path = str(Path(directory) / "history.db")
            broker = Broker(db_path=db_path, delivery_delay=0.01)
            ambul = Subscriber("amb", "Ambulance", ["emergency/medical"], broker)
            ambul.connect()

            report = make_report("MEDICAL", "Molo", "CRITICAL")
            broker.publish("emergency/medical", report)
            time.sleep(0.05)
            self.assertTrue(ambul.set_status(report["report_id"], "COMPLETED"))

            restarted_broker = Broker(db_path=db_path, delivery_delay=0.01)
            restarted_ambul = Subscriber(
                "amb", "Ambulance", ["emergency/medical"], restarted_broker
            )
            restarted_ambul.connect()

            restored = restarted_ambul.reports[report["report_id"]]
            self.assertEqual(restored.status, "COMPLETED")
            self.assertEqual(
                [item.report_id for item in restarted_ambul.drain_new_reports()],
                [report["report_id"]],
            )

    def test_status_changes_sync_to_command_center(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            broker = Broker(
                db_path=str(Path(directory) / "shared-status.db"), delivery_delay=0.01
            )
            fire = Subscriber("fire", "Fire Station", ["emergency/fire"], broker)
            command = Subscriber(
                "command_center",
                "Command Center",
                ["emergency/fire", "emergency/medical"],
                broker,
            )
            fire.connect()
            command.connect()

            report = make_report("FIRE", "Jaro", "HIGH")
            broker.publish("emergency/fire", report)
            time.sleep(0.05)
            self.assertTrue(fire.set_status(report["report_id"], "COMPLETED"))

            changed = command.refresh_reports()
            self.assertIn(command.reports[report["report_id"]], changed)
            self.assertEqual(command.reports[report["report_id"]].status, "COMPLETED")

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

    def test_repeated_reconnect_delivers_queued_report_once(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            broker = Broker(
                db_path=str(Path(directory) / "once.db"),
                delivery_delay=0.01,
            )
            delivered = []

            def callback(topic, report):
                delivered.append(report["report_id"])
                return True

            broker.register_subscriber(
                "sub",
                "Subscriber",
                ["*"],
                callback,
            )
            broker.set_online("sub", False)

            report = make_report("MEDICAL", "Molo", "CRITICAL")
            broker.publish("emergency/medical", report)
            broker.set_online("sub", True)
            broker.set_online("sub", True)
            time.sleep(0.05)

            self.assertEqual(delivered.count(report["report_id"]), 1)

    def test_offline_poll_does_not_surface_queued_report(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            broker = Broker(
                db_path=str(Path(directory) / "offline-poll.db"),
                delivery_delay=0.01,
            )
            ambul = Subscriber("amb", "Ambulance", ["emergency/medical"], broker)
            ambul.connect()
            ambul.disconnect()

            report = make_report("MEDICAL", "Molo", "CRITICAL")
            broker.publish("emergency/medical", report)
            time.sleep(0.05)

            self.assertEqual(ambul.refresh_reports(), [])
            self.assertNotIn(report["report_id"], ambul.reports)


if __name__ == "__main__":
    unittest.main()