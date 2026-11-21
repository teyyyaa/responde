"""
Publisher dashboard shared by the 911 Operator and Barangay Hotline UIs.
Requires: pip install customtkinter

Uses the colours, fonts and icons from ui/responder_dashboard.py so all
RESPONDE windows look the same.

Keyboard: Ctrl+Enter send report, Esc clear the form.
"""

from __future__ import annotations

import customtkinter as ctk

from clients.messages import INCIDENT_TYPES, SEVERITIES
from clients.publisher import ACKED, NOT_ROUTED, QUEUED, SENT, Publisher, SentReport
from ui import responder_dashboard as theme
from ui.responder_dashboard import Icon, empty_state, pill

f = theme.f
POLL_MS = 300
BANNER_MS = 6000
ERROR = "#b91c1c"
OK = "#166534"

# receipt state -> (symbol, label, text colour)
RECEIPT = {
    ACKED: ("✓", "Acknowledged", "#166534"),
    SENT: ("•", "Sent, waiting for ACK", "#1d4ed8"),
    QUEUED: ("⏳", "Offline, queued by broker", "#92400e"),
    NOT_ROUTED: ("✗", "Not subscribed to this topic", theme.FAINT),
}
RECEIPT_ORDER = [ACKED, SENT, QUEUED, NOT_ROUTED]


class SentCard(ctk.CTkFrame):
    """One sent report with its per-team delivery receipts."""

    def __init__(self, parent, entry: SentReport, on_retry):
        super().__init__(parent, fg_color=theme.CARD, corner_radius=10,
                         border_width=1, border_color=theme.BORDER)
        self.entry = entry
        self.on_retry = on_retry
        r = entry.report

        ctk.CTkFrame(self, width=4, height=10, corner_radius=2,
                     fg_color=theme.SEVERITY_BAR.get(r["severity"], theme.FAINT)).pack(
            side="left", fill="y", padx=(10, 0), pady=12)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")
        Icon(top, theme.TYPE_ICON.get(r["incident_type"], "dot"), size=16,
             color=theme.TEXT, bg=theme.CARD).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(top, text=r["incident_type"], text_color=theme.TEXT,
                     font=f(12, "bold")).pack(side="left")
        ctk.CTkLabel(top, text=f"  {entry.report_id}  →  {entry.topic}",
                     text_color=theme.FAINT, font=f(11)).pack(side="left")
        ctk.CTkLabel(top, text=entry.sent_at[-8:], text_color=theme.MUTED,
                     font=f(11)).pack(side="right")

        mid = ctk.CTkFrame(body, fg_color="transparent")
        mid.pack(fill="x", pady=(2, 6))
        ctk.CTkLabel(mid, text=r["location"], text_color=theme.TEXT, anchor="w",
                     font=f(15, "bold")).pack(side="left")
        pill(mid, r["severity"], theme.SEVERITY.get(r["severity"], (theme.MUTED, theme.TRACK))
             ).pack(side="right")

        self.receipts = ctk.CTkFrame(body, fg_color="transparent")
        self.receipts.pack(fill="x")
        self.refresh()

    def refresh(self):
        for w in self.receipts.winfo_children():
            w.destroy()
        e = self.entry
        if e.error:
            row = ctk.CTkFrame(self.receipts, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text=f"✗  Not sent: {e.error}", text_color=ERROR,
                         font=f(12, "bold"), anchor="w", wraplength=380,
                         justify="left").pack(side="left")
            ctk.CTkButton(row, text="Retry", width=70, height=28, corner_radius=6,
                          fg_color=theme.PRIMARY, hover_color="#b91c1c", text_color="white",
                          font=f(12, "bold"),
                          command=lambda: self.on_retry(e.report_id)).pack(side="right")
            return
        if not e.receipts:
            ctk.CTkLabel(self.receipts, text="Sent. No team is subscribed to this topic yet.",
                         text_color=theme.MUTED, font=f(12), anchor="w").pack(fill="x")
            return
        for state in RECEIPT_ORDER:
            for name in e.names(state):
                sym, label, colour = RECEIPT[state]
                row = ctk.CTkFrame(self.receipts, fg_color="transparent")
                row.pack(fill="x")
                ctk.CTkLabel(row, text=f"{sym}  {name}", text_color=colour if state != NOT_ROUTED
                             else theme.MUTED, font=f(12, "bold"), anchor="w",
                             height=20).pack(side="left")
                ctk.CTkLabel(row, text=label, text_color=colour, font=f(11),
                             anchor="e", height=20).pack(side="right")


class PublisherDashboard:
    def __init__(self, master, publisher: Publisher, title: str, accent: str = theme.ACCENT,
                 location_hint: str = ""):
        theme._resolve_fonts(master)
        self.master = master
        self.pub = publisher
        self.title = title
        self.accent = accent
        self.location_hint = location_hint
        self.cards: dict[str, SentCard] = {}
        self._banner_job = None

        master.title(f"RESPONDE · {title}")
        master.geometry("1200x760")
        master.minsize(1000, 640)
        master.configure(fg_color=theme.BG)

        self._build_header()
        self._build_body()
        self._bind_keys()
        self._refresh_stats()
        self._poll()

    # Header (same style as the responder dashboards)
    def _build_header(self):
        header = ctk.CTkFrame(self.master, fg_color=theme.HEADER, corner_radius=0, height=76)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkFrame(self.master, fg_color=self.accent, height=3, corner_radius=0).pack(fill="x")

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left", padx=22)
        ctk.CTkLabel(brand, text="R", width=40, height=40, corner_radius=10,
                     fg_color=theme.PRIMARY, text_color="white",
                     font=f(20, "bold")).pack(side="left", pady=18)
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left", padx=12)
        ctk.CTkLabel(names, text="RESPONDE", text_color=theme.HEADER_TEXT, font=f(18, "bold"),
                     anchor="w", height=22).pack(anchor="w")
        ctk.CTkLabel(names, text=self.title, text_color=theme.HEADER_MUTED, font=f(12),
                     anchor="w", height=18).pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", padx=22)
        ctk.CTkLabel(right, text=f"  Source: {self.pub.source}  ", corner_radius=14, height=28,
                     fg_color="#2c3a4d", text_color=theme.HEADER_TEXT,
                     font=f(12, "bold")).pack(side="right", padx=(14, 0))
        ctk.CTkFrame(right, fg_color=theme.HEADER_LINE, width=1, height=36).pack(side="right", padx=8)

        self.stat_labels = {}
        for key, label, colour in (("acked", "CONFIRMED", "#4ade80"),
                                   ("queued", "QUEUED", "#fbbf24"),
                                   ("sent", "SENT", "#93c5fd")):
            box = ctk.CTkFrame(right, fg_color="transparent")
            box.pack(side="right", padx=14)
            num = ctk.CTkLabel(box, text="0", text_color=colour, font=f(22, "bold"), height=26)
            num.pack()
            ctk.CTkLabel(box, text=label, text_color=theme.HEADER_MUTED, font=f(11, "bold"),
                         height=14).pack()
            self.stat_labels[key] = num

    # Body: form (left) + sent reports (right)
    def _build_body(self):
        body = ctk.CTkFrame(self.master, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(18, 10))
        body.grid_columnconfigure(0, weight=2, uniform="cols")
        body.grid_columnconfigure(1, weight=3, uniform="cols")
        body.grid_rowconfigure(0, weight=1)

        self._build_form(body)

        sent = ctk.CTkFrame(body, fg_color=theme.PANEL, corner_radius=14,
                            border_width=1, border_color=theme.BORDER)
        sent.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        head = ctk.CTkFrame(sent, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(head, text="Sent Reports", text_color=theme.TEXT,
                     font=f(16, "bold")).pack(side="left")
        ctk.CTkLabel(head, text="Delivery confirmation per team", text_color=theme.MUTED,
                     font=f(12)).pack(side="right")
        self.sent_list = ctk.CTkScrollableFrame(sent, fg_color="transparent",
                                                scrollbar_button_color=theme.BORDER,
                                                scrollbar_button_hover_color=theme.BORDER_HOVER)
        self.sent_list.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self.sent_empty = empty_state(
            self.sent_list, "radar", "No reports sent yet",
            "Reports you send appear here with which teams received them, "
            "which are queued while offline, and which confirmed (ACK).", theme.PANEL)
        self.sent_empty.pack(fill="x")

        ctk.CTkLabel(self.master, text="Keyboard:   Ctrl+Enter  send report     Esc  clear form",
                     text_color=theme.TEXT, font=f(11), anchor="w").pack(fill="x", padx=22, pady=(0, 8))

    def _build_form(self, parent):
        card = ctk.CTkFrame(parent, fg_color=theme.PANEL, corner_radius=14,
                            border_width=1, border_color=theme.BORDER)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        ctk.CTkLabel(card, text="Report Emergency", text_color=theme.TEXT, font=f(16, "bold"),
                     anchor="w").pack(fill="x", padx=18, pady=(14, 4))

        self.banner = ctk.CTkLabel(card, text="", corner_radius=8, font=f(12, "bold"),
                                   anchor="w", justify="left", wraplength=380)
        self.errors = {}

        def label(text, key):
            ctk.CTkLabel(card, text=text, text_color=theme.FAINT, font=f(11, "bold"),
                         anchor="w").pack(fill="x", padx=18, pady=(10, 3))

        def error_label(key):
            lbl = ctk.CTkLabel(card, text="", text_color=ERROR, font=f(11), anchor="w", height=14)
            lbl.pack(fill="x", padx=18)
            self.errors[key] = lbl

        seg = dict(font=f(13, "bold"), height=38, selected_color=self.accent,
                   selected_hover_color=self.accent, unselected_color=theme.CARD,
                   unselected_hover_color=theme.TRACK, fg_color=theme.TRACK,
                   text_color=theme.TEXT)

        label("INCIDENT TYPE", "incident_type")
        self.type_btn = ctk.CTkSegmentedButton(card, values=list(INCIDENT_TYPES), **seg)
        self.type_btn.pack(fill="x", padx=18)
        error_label("incident_type")

        label("LOCATION", "location")
        self.location = ctk.CTkEntry(card, height=40, corner_radius=8, fg_color=theme.CARD,
                                     border_color=theme.BORDER, text_color=theme.TEXT, font=f(14),
                                     placeholder_text=self.location_hint or "e.g. Brgy. Tabuc Suba",
                                     placeholder_text_color=theme.FAINT)
        self.location.pack(fill="x", padx=18)
        error_label("location")

        label("PRIORITY", "severity")
        self.sev_btn = ctk.CTkSegmentedButton(card, values=list(reversed(SEVERITIES)), **seg)
        self.sev_btn.pack(fill="x", padx=18)
        error_label("severity")

        label("DESCRIPTION (optional)", "description")
        self.description = ctk.CTkTextbox(card, height=86, corner_radius=8, fg_color=theme.CARD,
                                          border_width=2, border_color=theme.BORDER,
                                          text_color=theme.TEXT, font=f(13), wrap="word")
        self.description.pack(fill="x", padx=18)
        error_label("description")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill="x", padx=18, pady=(12, 8))
        self.send_btn = ctk.CTkButton(btns, text="SEND REPORT", height=46, corner_radius=10,
                                      fg_color=theme.PRIMARY, hover_color="#b91c1c",
                                      text_color="white", font=f(14, "bold"), command=self._send)
        self.send_btn.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(btns, text="Clear", width=80, height=46, corner_radius=10,
                      fg_color=theme.CARD, hover_color=theme.TRACK, text_color=theme.TEXT,
                      border_width=1, border_color=theme.BORDER, font=f(13, "bold"),
                      command=self._clear).pack(side="left", padx=(8, 0))
        self.banner.pack(fill="x", padx=18, pady=(4, 12))

    def _bind_keys(self):
        self.master.bind("<Control-Return>", lambda _e: self._send())
        self.master.bind("<Escape>", lambda _e: self._clear())

    # Actions
    def _form_values(self):
        return (self.type_btn.get() or "", self.location.get(), self.sev_btn.get() or "",
                self.description.get("1.0", "end").strip())

    def _send(self):
        incident_type, location, severity, description = self._form_values()
        problems = self.pub.check_form(incident_type, location, severity, description)
        for key, lbl in self.errors.items():
            lbl.configure(text=problems.get(key, ""))
        self.location.configure(border_color=ERROR if "location" in problems else theme.BORDER)
        if problems:
            self._show_banner("Please fix the highlighted fields.", error=True)
            if "location" in problems:
                self.location.focus_set()
            return

        entry = self.pub.send(incident_type, location, severity, description)
        self._add_card(entry)
        if entry.error:
            self._show_banner(f"Could not send {entry.report_id}: {entry.error}\n"
                              "The report is kept on the right. Press Retry.", error=True)
            return
        lines = [f"✓  {entry.report_id} sent to {entry.topic}"]
        if entry.names(SENT):
            lines.append("Delivered to: " + ", ".join(entry.names(SENT)))
        if entry.names(QUEUED):
            lines.append("Queued (offline): " + ", ".join(entry.names(QUEUED)))
        self._show_banner("\n".join(lines))
        self._clear(keep_banner=True)

    def _retry(self, report_id):
        entry = self.pub.resend(report_id)
        self.cards[report_id].refresh()
        self._refresh_stats()
        if entry.error:
            self._show_banner(f"Retry failed for {report_id}: {entry.error}", error=True)
        else:
            self._show_banner(f"✓  {report_id} sent to {entry.topic}")

    def _clear(self, keep_banner=False):
        self.location.delete(0, "end")
        self.description.delete("1.0", "end")
        self.type_btn.set("")
        self.sev_btn.set("")
        for lbl in self.errors.values():
            lbl.configure(text="")
        self.location.configure(border_color=theme.BORDER)
        if not keep_banner:
            self._hide_banner()

    def _show_banner(self, text, error=False):
        fg, bg = (ERROR, "#f6d3d3") if error else (OK, "#cfe8d6")
        text = "\n".join(f"  {line}" for line in text.splitlines())
        self.banner.configure(text=text, text_color=fg, fg_color=bg)
        if self._banner_job:
            self.master.after_cancel(self._banner_job)
        self._banner_job = self.master.after(BANNER_MS, self._hide_banner)

    def _hide_banner(self):
        self.banner.configure(text="", fg_color="transparent")
        self._banner_job = None

    # Sent list
    def _add_card(self, entry):
        self.sent_empty.pack_forget()
        card = SentCard(self.sent_list, entry, self._retry)
        self.cards[entry.report_id] = card
        newest = getattr(self, "_newest", None)
        if newest is not None:
            card.pack(fill="x", padx=6, pady=5, before=newest)   # newest on top
        else:
            card.pack(fill="x", padx=6, pady=5)
        self._newest = card
        self._refresh_stats()

    def _refresh_stats(self):
        counts = {"sent": 0, "queued": 0, "acked": 0}
        for e in self.pub.history:
            if e.error:
                continue
            counts["sent"] += 1
            states = [s for s in e.receipts.values() if s != NOT_ROUTED]
            if QUEUED in states:
                counts["queued"] += 1
            if states and all(s == ACKED for s in states):
                counts["acked"] += 1
        for k, v in counts.items():
            self.stat_labels[k].configure(text=str(v))

    # Poll the broker for new ACKs
    def _poll(self):
        changed = self.pub.refresh_receipts()
        for entry in changed:
            card = self.cards.get(entry.report_id)
            if card:
                card.refresh()
        if changed:
            self._refresh_stats()
        self.master.after(POLL_MS, self._poll)
