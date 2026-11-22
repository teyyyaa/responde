"""Topic-routing tests for the persistent broker."""

import tempfile
import unittest
from pathlib import Path

from broker.broker import Broker
from clients.messages import make_report
from clients.subscriber import Subscriber


class RoutingTests(unittest.TestCase):
    def test_fire_only_reaches_fire_and_command_topics(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            broker = Broker(db_path=str(Path(directory) / "routing.db"), delivery_delay=0.01)
            fire = Subscriber("fire", "Fire", ["emergency/fire"], broker)
            amb = Subscriber("amb", "Ambulance", ["emergency/medical"], broker)
            cmd = Subscriber("cmd", "Command", ["emergency/fire", "emergency/medical"], broker)
            for subscriber in (fire, amb, cmd):
                subscriber.connect()

            report = make_report("FIRE", "Iloilo", "HIGH")
            broker.publish("emergency/fire", report)

            import time
            time.sleep(0.05)
            self.assertIn(report["report_id"], fire.reports)
            self.assertIn(report["report_id"], cmd.reports)
            self.assertNotIn(report["report_id"], amb.reports)


if __name__ == "__main__":
    unittest.main()