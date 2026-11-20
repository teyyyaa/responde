"""Command Center (CDRRMO) dashboard: receives all reports."""

from clients.subscriber import Subscriber
from ui.responder_dashboard import ResponderDashboard

SUBSCRIBER_ID = "command_center"
NAME = "Command Center (CDRRMO)"
TOPICS = ["emergency/fire", "emergency/medical"]
TITLE = "Command Center Dashboard"
ACCENT = "#0d9488"


def open_dashboard(master, broker) -> ResponderDashboard:
    """Open this dashboard in `master` (a CTk or CTkToplevel window)."""
    return ResponderDashboard(master, Subscriber(SUBSCRIBER_ID, NAME, TOPICS, broker), TITLE, ACCENT)
