"""Fire Station dashboard: receives FIRE reports."""

from clients.subscriber import Subscriber
from ui.responder_dashboard import ResponderDashboard

SUBSCRIBER_ID = "fire_station"
NAME = "Fire Station (BFP)"
TOPICS = ["emergency/fire"]
TITLE = "Fire Station Dashboard"
ACCENT = "#ef4444"


def open_dashboard(master, broker) -> ResponderDashboard:
    """Open this dashboard in `master` (a CTk or CTkToplevel window)."""
    return ResponderDashboard(master, Subscriber(SUBSCRIBER_ID, NAME, TOPICS, broker), TITLE, ACCENT)