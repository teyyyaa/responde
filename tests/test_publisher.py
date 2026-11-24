"""Tests for clients/publisher.py. Run: python -m unittest tests.test_publisher -v"""

import tempfile
import time
import unittest
from pathlib import Path

from broker.broker import Broker
from clients.mock_broker import MockBroker
from clients.publisher import (
    ACKED,
    NOT_ROUTED,
    QUEUED,
    SENT,
    SOURCE_BARANGAY,
    SOURCE_OPERATOR,
    Publisher,
)
from clients.subscriber import Subscriber


def wait_for(cond, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


class FlakyBroker(MockBroker):
    """Mock broker that fails the next publish, to test Retry."""

    def __init__(self):
        super().__init__(delivery_delay=0.01)
        self.fail_next = True

    def publish(self, topic, report):
        if self.fail_next:
            self.fail_next = False
            raise ConnectionError("broker unreachable")
        return super().publish(topic, report)


class MinimalBroker:
    """Only the required interface: publish() -> (delivered, queued)."""

    def __init__(self):
        self.published = []

    def publish(self, topic, report):
        self.published.append((topic, report))
        return ["Fire Station (BFP)"], []


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.broker = MockBroker(delivery_delay=0.01)
        self.fire = Subscriber("fire_station", "Fire Station (BFP)", ["emergency/fire"], self.broker)
        self.amb = Subscriber("ambulance", "Ambulance Team", ["emergency/medical"], self.broker)
        self.cmd = Subscriber("command_center", "Command Center (CDRRMO)",
                              ["emergency/fire", "emergency/medical"], self.broker)
        for s in (self.fire, self.amb, self.cmd):
            s.connect()
        self.op = Publisher(SOURCE_OPERATOR, self.broker)

    def test_invalid_form_not_published(self):
        errors = Publisher.check_form("FLOOD", "  ", "URGENT")
        self.assertEqual(set(errors), {"incident_type", "location", "severity"})
        with self.assertRaises(ValueError):
            self.op.send("FIRE", "", "HIGH")
        self.assertEqual(self.op.history, [])
        self.assertEqual(self.broker.log, [])

    def test_fire_routing_receipts(self):
        """FIRE -> Fire Station + Command Center, not Ambulance (PDF example)."""
        e = self.op.send("FIRE", "Brgy. Tabuc Suba", "CRITICAL", "House fire")
        self.assertEqual(e.topic, "emergency/fire")
        self.assertEqual(e.receipts["Fire Station (BFP)"], SENT)
        self.assertEqual(e.receipts["Command Center (CDRRMO)"], SENT)
        self.assertEqual(e.receipts["Ambulance Team"], NOT_ROUTED)
        def both_acked():
            self.op.refresh_receipts()
            return sorted(e.names(ACKED)) == ["Command Center (CDRRMO)", "Fire Station (BFP)"]
        self.assertTrue(wait_for(both_acked))
        self.assertNotIn(e.report_id, self.amb.reports)

    def test_report_arrives_on_dashboards_with_source(self):
        e = self.op.send("MEDICAL", "Jaro Plaza", "HIGH", "Collapsed person")
        self.assertTrue(wait_for(lambda: e.report_id in self.amb.reports))
        got = self.amb.reports[e.report_id]
        self.assertEqual(got.source, SOURCE_OPERATOR)
        self.assertEqual(got.location, "Jaro Plaza")
        self.assertEqual(got.severity, "HIGH")
        self.assertEqual(got.topic, "emergency/medical")

    def test_offline_ambulance_queued_then_acked(self):
        """Section 5 scenario: ambulance offline -> queued -> reconnect -> ACK."""
        self.amb.disconnect()
        e = self.op.send("MEDICAL", "Molo", "CRITICAL", "Cardiac arrest")
        self.assertEqual(e.receipts["Ambulance Team"], QUEUED)
        time.sleep(0.1)
        self.op.refresh_receipts()
        self.assertEqual(e.receipts["Ambulance Team"], QUEUED)
        self.amb.connect()
        def amb_acked():
            self.op.refresh_receipts()
            return e.receipts["Ambulance Team"] == ACKED
        self.assertTrue(wait_for(amb_acked))
        self.assertIn(e.report_id, self.amb.reports)

    def test_broker_failure_then_retry_same_id(self):
        broker = FlakyBroker()
        fire = Subscriber("fire_station", "Fire Station (BFP)", ["emergency/fire"], broker)
        fire.connect()
        pub = Publisher(SOURCE_BARANGAY, broker)
        e = pub.send("FIRE", "La Paz", "MEDIUM")
        self.assertIn("unreachable", e.error)
        self.assertEqual(len(pub.history), 1)
        again = pub.resend(e.report_id)
        self.assertIs(again, e)
        self.assertFalse(e.error)
        self.assertTrue(wait_for(lambda: e.report_id in fire.reports))
        self.assertEqual(fire.reports[e.report_id].source, SOURCE_BARANGAY)

    def test_sent_history_is_restored_for_its_source(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            db_path = str(Path(directory) / "publisher-history.db")
            broker = Broker(db_path=db_path, delivery_delay=0.01)
            fire = Subscriber("fire_station", "Fire Station", ["emergency/fire"], broker)
            fire.connect()

            operator = Publisher(SOURCE_OPERATOR, broker)
            barangay = Publisher(SOURCE_BARANGAY, broker)
            operator_report = operator.send("FIRE", "Jaro", "HIGH")
            barangay_report = barangay.send("FIRE", "Molo", "MEDIUM")

            def both_acked():
                operator.refresh_receipts()
                barangay.refresh_receipts()
                return (
                    operator_report.receipts.get("Fire Station") == ACKED
                    and barangay_report.receipts.get("Fire Station") == ACKED
                )

            self.assertTrue(wait_for(both_acked))

            restarted_broker = Broker(db_path=db_path, delivery_delay=0.01)
            restarted_fire = Subscriber(
                "fire_station", "Fire Station", ["emergency/fire"], restarted_broker
            )
            restarted_fire.connect()
            restored_operator = Publisher(SOURCE_OPERATOR, restarted_broker)
            restored_barangay = Publisher(SOURCE_BARANGAY, restarted_broker)

            self.assertEqual(
                [entry.report_id for entry in restored_operator.history],
                [operator_report.report_id],
            )
            self.assertEqual(
                [entry.report_id for entry in restored_barangay.history],
                [barangay_report.report_id],
            )
            self.assertEqual(
                restored_operator.get(operator_report.report_id).receipts["Fire Station"],
                ACKED,
            )

    def test_resend_is_not_shown_twice(self):
        e = self.op.send("FIRE", "Mandurriao", "LOW")
        self.assertTrue(wait_for(lambda: e.report_id in self.fire.reports))
        self.op.resend(e.report_id)
        self.assertTrue(wait_for(lambda: any(ev.event == "DUPLICATE" for ev in self.fire.history)))
        self.assertEqual(len(self.fire.drain_new_reports()), 1)

    def test_works_with_minimal_broker(self):
        broker = MinimalBroker()
        pub = Publisher(SOURCE_OPERATOR, broker)
        e = pub.send("fire", " Arevalo ", "high")
        self.assertEqual(broker.published[0][0], "emergency/fire")
        self.assertEqual(e.report["location"], "Arevalo")
        self.assertEqual(e.report["severity"], "HIGH")
        self.assertEqual(e.receipts, {"Fire Station (BFP)": SENT})
        self.assertEqual(pub.refresh_receipts(), [])


if __name__ == "__main__":
    unittest.main()
