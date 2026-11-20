"""Shared report format and topics used by publishers, the broker and subscribers."""

from __future__ import annotations

import uuid
from datetime import datetime

INCIDENT_TYPES = ("FIRE", "MEDICAL")
SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
TOPIC_FOR_TYPE = {"FIRE": "emergency/fire", "MEDICAL": "emergency/medical"}
REQUIRED_FIELDS = ("report_id", "incident_type", "location", "severity")


def make_report(incident_type: str, location: str, severity: str,
                description: str = "", source: str = "") -> dict:
    """Build a report dict in the agreed format."""
    return {
        "report_id": f"R-{uuid.uuid4().hex[:8].upper()}",
        "incident_type": incident_type.upper(),
        "location": location.strip(),
        "severity": severity.upper(),
        "description": description.strip(),
        "source": source,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def topic_for(report: dict) -> str:
    """Topic a report should be published to, e.g. 'emergency/fire'."""
    return TOPIC_FOR_TYPE[report["incident_type"]]


def validate_report(report) -> str | None:
    """Return an error message, or None if the report is valid."""
    if not isinstance(report, dict):
        return "message is not a report"
    missing = [f for f in REQUIRED_FIELDS if not str(report.get(f, "")).strip()]
    if missing:
        return f"missing fields: {', '.join(missing)}"
    if str(report["incident_type"]).upper() not in INCIDENT_TYPES:
        return f"invalid incident type: {report['incident_type']}"
    if str(report["severity"]).upper() not in SEVERITIES:
        return f"invalid severity: {report['severity']}"
    return None