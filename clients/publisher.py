"""
Publisher client shared by the 911 Operator and Barangay Hotline dashboards.

Operators use this to send reports without knowing broker internals.

Uses:
    clients/messages.py   make_report, validate_report, topic_for (shared format)
    broker.publish(topic, report) -> (delivered_names, queued_names)

Optional, used only if the broker has them (the mock broker does):
    broker.subscribers    {subscriber_id: {"name": ..., "topics": [...]}}
                          -> shows teams the report was NOT routed to
    broker.log            [("ACK", subscriber_id, report_id), ...]
                          -> upgrades "sent"/"queued" to "acknowledged"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from clients.messages import (
    INCIDENT_TYPES,
    SEVERITIES,
    make_report,
    topic_for,
    validate_report,
)

SOURCE_OPERATOR = "911 Operator"
SOURCE_BARANGAY = "Barangay Hotline"

MAX_LOCATION = 120
MAX_DESCRIPTION = 500

# Per-team delivery state shown to the operator
SENT = "SENT"              # team was online; waiting for its ACK
QUEUED = "QUEUED"          # team was offline; broker is holding the report
ACKED = "ACKED"            # team confirmed receipt
NOT_ROUTED = "NOT_ROUTED"  # team is not subscribed to this topic


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class SentReport:
    report: dict
    topic: str
    sent_at: str = field(default_factory=now_str)
    receipts: dict = field(default_factory=dict)   # team name -> SENT/QUEUED/ACKED/NOT_ROUTED
    error: str = ""                                # set if the broker refused / failed

    @property
    def report_id(self) -> str:
        return self.report["report_id"]

    @property
    def ok(self) -> bool:
        return not self.error

    def names(self, state: str) -> list[str]:
        return [n for n, s in self.receipts.items() if s == state]


class Publisher:
    def __init__(self, source: str, broker):
        self.source = source
        self.broker = broker
        self.history: list[SentReport] = []      # newest last
        self._by_id: dict[str, SentReport] = {}
        self._log_pos = 0

    # Form validation (field -> message); empty dict means OK
    @staticmethod
    def check_form(incident_type: str, location: str, severity: str,
                   description: str = "") -> dict[str, str]:
        errors = {}
        if str(incident_type).upper() not in INCIDENT_TYPES:
            errors["incident_type"] = f"Choose one of: {', '.join(INCIDENT_TYPES)}."
        loc = (location or "").strip()
        if not loc:
            errors["location"] = "Location is required."
        elif len(loc) < 3:
            errors["location"] = "Location is too short."
        elif len(loc) > MAX_LOCATION:
            errors["location"] = f"Location must be at most {MAX_LOCATION} characters."
        if str(severity).upper() not in SEVERITIES:
            errors["severity"] = f"Choose one of: {', '.join(SEVERITIES)}."
        if len((description or "").strip()) > MAX_DESCRIPTION:
            errors["description"] = f"Description must be at most {MAX_DESCRIPTION} characters."
        return errors

    # Sending
    def send(self, incident_type: str, location: str, severity: str,
             description: str = "") -> SentReport:
        """Validate, build and publish a report. Raises ValueError on bad input."""
        errors = self.check_form(incident_type, location, severity, description)
        if errors:
            raise ValueError(" ".join(errors.values()))
        report = make_report(incident_type, location, severity, description, self.source)
        problem = validate_report(report)
        if problem:                      # should not happen after check_form
            raise ValueError(problem)
        return self._publish(report)

    def resend(self, report_id: str) -> SentReport:
        """Publish the same report again (same report_id) after a failure.
        Subscribers ignore duplicates, so this is safe (at-least-once)."""
        old = self._by_id[report_id]
        return self._publish(old.report, existing=old)

    def _publish(self, report: dict, existing: SentReport | None = None) -> SentReport:
        topic = topic_for(report)
        entry = existing or SentReport(report=report, topic=topic)
        entry.error = ""
        try:
            delivered, queued = self.broker.publish(topic, report)
        except Exception as exc:          # broker down or refused the report
            entry.error = str(exc) or exc.__class__.__name__
            delivered, queued = [], []
        else:
            receipts = {name: SENT for name in delivered}
            receipts.update({name: QUEUED for name in queued})
            for name in self._team_names():
                receipts.setdefault(name, NOT_ROUTED)
            # keep ACKs already received for this report (on resend)
            for name, state in entry.receipts.items():
                if state == ACKED:
                    receipts[name] = ACKED
            entry.receipts = receipts
        if existing is None:
            self.history.append(entry)
            self._by_id[entry.report_id] = entry
        self.refresh_receipts()
        return entry

    # Delivery confirmations
    def refresh_receipts(self) -> list[SentReport]:
        """Check the broker for new ACKs. Returns reports whose receipts changed."""
        log = getattr(self.broker, "log", None)
        if not isinstance(log, list):
            return []
        new = log[self._log_pos:]
        self._log_pos += len(new)
        changed = []
        for item in new:
            if len(item) < 3 or item[0] != "ACK":
                continue
            entry = self._by_id.get(str(item[2]))
            name = self._team_name(item[1])
            if entry and name and entry.receipts.get(name) != ACKED:
                entry.receipts[name] = ACKED
                if entry not in changed:
                    changed.append(entry)
        return changed

    def get(self, report_id: str) -> SentReport | None:
        return self._by_id.get(report_id)

    # Helpers
    def _subscribers(self) -> dict:
        subs = getattr(self.broker, "subscribers", None)
        return subs if isinstance(subs, dict) else {}

    def _team_names(self) -> list[str]:
        return [s.get("name", sid) for sid, s in self._subscribers().items()]

    def _team_name(self, subscriber_id) -> str | None:
        sub = self._subscribers().get(subscriber_id)
        return sub.get("name", subscriber_id) if sub else None
