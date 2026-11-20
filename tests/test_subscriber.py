"""Tests for clients/subscriber.py. Run: python -m unittest tests.test_subscriber -v"""

import time
import unittest

from clients.messages import make_report
from clients.mock_broker import MockBroker
from clients.subscriber import (
    STATUS_COMPLETED,
    STATUS_RECEIVED,
    STATUS_RESPONDING,
    Subscriber,
)


def wait_for(cond, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


class SubscriberTests(unittest.TestCase):
    def setUp(self):
        self.broker = MockBroker(delivery_delay=0.01)
        self.fire = Subscriber("fire", "Fire Station", ["emergency/fire"], self.broker)
        self.amb = Subscriber("amb", "Ambulance", ["emergency/medical"], self.broker)
        self.cmd = Subscriber("cmd", "Command Center",
                              ["emergency/fire", "emergency/medical"], self.broker)
        for s in (self.fire, self.amb, self.cmd):
            s.connect()

    def test_topic_filtering(self):
        r = make_report("FIRE", "Brgy. Tabuc Suba", "CRITICAL", "House fire")
        self.broker.publish("emergency/fire", r)
        self.assertTrue(wait_for(lambda: r["report_id"] in self.cmd.reports))
        self.assertTrue(wait_for(lambda: r["report_id"] in self.fire.reports))
        time.sleep(0.1)
        self.assertNotIn(r["report_id"], self.amb.reports)

    def test_ack_sent(self):
        r = make_report("MEDICAL", "Jaro", "HIGH")
        self.broker.publish("emergency/medical", r)
        self.assertTrue(wait_for(lambda: ("ACK", "amb", r["report_id"]) in self.broker.log))
        self.assertNotIn(r["report_id"], self.broker.unacked["amb"])

    def test_offline_then_redelivery(self):
        self.amb.disconnect()
        r = make_report("MEDICAL", "Molo", "CRITICAL", "Cardiac arrest")
        self.broker.publish("emergency/medical", r)
        time.sleep(0.1)
        self.assertNotIn(r["report_id"], self.amb.reports)
        self.amb.connect()
        self.assertTrue(wait_for(lambda: r["report_id"] in self.amb.reports))

    def test_duplicates_ignored(self):
        r = make_report("FIRE", "La Paz", "MEDIUM")
        self.fire._on_message("emergency/fire", r)
        self.fire._on_message("emergency/fire", r)
        self.assertEqual(len(self.fire.drain_new_reports()), 1)
        self.assertTrue(any(e.event == "DUPLICATE" for e in self.fire.history))

    def test_invalid_report_nacked(self):  # missing location and severity
        ok = self.fire._on_message("emergency/fire", {"report_id": "X-1", "incident_type": "FIRE"})
        self.assertFalse(ok)
        self.assertIn(("NACK", "fire", "X-1"), self.broker.log)

    def test_status_moves_forward_only(self):
        r = make_report("FIRE", "Mandurriao", "HIGH")
        self.fire._on_message("emergency/fire", r)
        rid = r["report_id"]
        self.assertTrue(self.fire.set_status(rid, STATUS_RECEIVED))
        self.assertTrue(self.fire.set_status(rid, STATUS_RESPONDING))
        self.assertFalse(self.fire.set_status(rid, STATUS_RECEIVED))  # backward
        self.assertTrue(self.fire.set_status(rid, STATUS_COMPLETED))
        self.assertEqual(self.broker.statuses[("fire", rid)], STATUS_COMPLETED)


if __name__ == "__main__":
    unittest.main()
    