"""Ambulance dashboard: receives MEDICAL reports."""

from clients.subscriber import Subscriber
from ui.responder_dashboard import ResponderDashboard

SUBSCRIBER_ID = "ambulance"
NAME = "Ambulance Team"
TOPICS = ["emergency/medical"]
TITLE = "Ambulance Dashboard"
ACCENT = "#3b82f6"


def open_dashboard(master, broker) -> ResponderDashboard:
    """Open this dashboard in `master` (a CTk or CTkToplevel window)."""
    return ResponderDashboard(master, Subscriber(SUBSCRIBER_ID, NAME, TOPICS, broker), TITLE, ACCENT)
