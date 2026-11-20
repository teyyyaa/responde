"""Barangay Emergency Hotline dashboard: publishes FIRE and MEDICAL reports."""

from clients.publisher import SOURCE_BARANGAY, Publisher
from ui.publisher_dashboard import PublisherDashboard

TITLE = "Barangay Hotline Dashboard"
ACCENT = "#7c3aed"


def open_dashboard(master, broker) -> PublisherDashboard:
    """Open this dashboard in `master` (a CTk or CTkToplevel window)."""
    return PublisherDashboard(master, Publisher(SOURCE_BARANGAY, broker), TITLE, ACCENT,
                              location_hint="e.g. Purok 3, Brgy. Tabuc Suba")
