"""911 Operator dashboard: publishes FIRE and MEDICAL reports."""

from clients.publisher import SOURCE_OPERATOR, Publisher
from ui.publisher_dashboard import PublisherDashboard

TITLE = "911 Operator Dashboard"
ACCENT = "#dc2626"


def open_dashboard(master, broker) -> PublisherDashboard:
    """Open this dashboard in `master` (a CTk or CTkToplevel window)."""
    return PublisherDashboard(master, Publisher(SOURCE_OPERATOR, broker), TITLE, ACCENT)
