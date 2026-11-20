"""
Responder dashboard shared by the Fire Station, Ambulance and Command Center UIs.
Requires: pip install customtkinter

Keyboard: Up/Down select alert, 1/2/3 set Received/Responding/Completed, Esc closes popup.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

import customtkinter as ctk

from clients.subscriber import (
    STATUS_COMPLETED,
    STATUS_NEW,
    STATUS_ORDER,
    STATUS_RECEIVED,
    STATUS_RESPONDING,
    Subscriber,
)

# Theme (text colours meet WCAG 4.5:1 contrast)
ctk.set_appearance_mode("light")

BG = "#cdd5df"
PANEL = "#e4e9ef"
CARD = "#eef1f5"
CARD_SELECTED = "#f6f8fa"
BORDER = "#bcc6d2"
BORDER_HOVER = "#8d99a8"
TRACK = "#d3dae3"
TEXT = "#1e293b"
MUTED = "#536175"
FAINT = "#5a6678"
DISABLED_BG = "#d5dce4"
DISABLED_TEXT = "#5a6678"

HEADER = "#1e2a3a"
HEADER_TEXT = "#f1f5f9"
HEADER_MUTED = "#a3b1c2"
HEADER_LINE = "#334155"

PRIMARY = "#dc2626"
ACCENT = "#2563eb"

# (text colour, background colour)
SEVERITY = {
    "CRITICAL": ("#b91c1c", "#f6d3d3"),
    "HIGH": ("#9a3412", "#f5dcc4"),
    "MEDIUM": ("#854d0e", "#efe4b0"),
    "LOW": ("#166534", "#cfe8d6"),
}
SEVERITY_BAR = {"CRITICAL": "#dc2626", "HIGH": "#ea580c", "MEDIUM": "#ca8a04", "LOW": "#16a34a"}
STATUS = {
    STATUS_NEW: ("#b91c1c", "#f6d3d3"),
    STATUS_RECEIVED: ("#1d4ed8", "#d1def5"),
    STATUS_RESPONDING: ("#92400e", "#f1e1bd"),
    STATUS_COMPLETED: ("#166534", "#cfe8d6"),
}
STEP_DOT = {STATUS_NEW: "#dc2626", STATUS_RECEIVED: "#2563eb",
            STATUS_RESPONDING: "#b45309", STATUS_COMPLETED: "#15803d"}
STATUS_BUTTON = {         # (colour, hover)
    STATUS_RECEIVED: ("#2563eb", "#1d4ed8"),
    STATUS_RESPONDING: ("#b45309", "#92400e"),
    STATUS_COMPLETED: ("#15803d", "#166534"),
}
SHORTCUT = {STATUS_RECEIVED: "1", STATUS_RESPONDING: "2", STATUS_COMPLETED: "3"}
TYPE_ICON = {"FIRE": "fire", "MEDICAL": "medical"}

POLL_MS = 200
TOAST_MS = 5000
FEEDBACK_MS = 3000
REDUCE_MOTION = False     # set True to stop the alert border pulsing

# Fonts: uses Fira Sans / Fira Code if found in ui/assets/fonts, else system fonts
_FONTS_DIR = Path(__file__).parent / "assets" / "fonts"
for _ttf in sorted(_FONTS_DIR.glob("*.ttf")):
    try:
        ctk.FontManager.load_font(str(_ttf))
    except Exception:
        pass

FONT = "TkDefaultFont"
MONO = "TkFixedFont"
_fonts_ready = False


def _resolve_fonts(root):
    global FONT, MONO, _fonts_ready
    if _fonts_ready:
        return
    families = set(tkfont.families(root))
    FONT = next((f for f in ("Fira Sans", "Segoe UI", "SF Pro Text", "Helvetica Neue",
                             "DejaVu Sans") if f in families), "TkDefaultFont")
    MONO = next((f for f in ("Fira Code", "Consolas", "Menlo", "DejaVu Sans Mono")
                 if f in families), "TkFixedFont")
    _fonts_ready = True


def f(size, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


# Small helpers
def pill(parent, text, colours):
    fg, bg = colours
    return ctk.CTkLabel(parent, text=f"  {text}  ", fg_color=bg, text_color=fg,
                        corner_radius=6, height=22, font=f(11, "bold"))


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def bind_tree(widget, event, handler):
    for w in walk(widget):
        w.bind(event, handler, add="+")


def hand_cursor(widget):
    for w in walk(widget):
        try:
            w.tk.call(w._w, "configure", "-cursor", "hand2")
        except tk.TclError:
            pass


class Icon(tk.Canvas):
    """Small vector icons drawn on a canvas."""

    def __init__(self, parent, kind, size=18, color=TEXT, bg=CARD):
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self.kind, self.size = kind, size
        self.draw(color)

    def _pts(self, pts):
        k = self.size / 24
        return [v * k for xy in pts for v in xy]

    def draw(self, color):
        self.delete("all")
        k = self.size / 24
        bg = self["bg"]
        if self.kind == "fire":
            self.create_polygon(self._pts([(12, 1.5), (15, 6.5), (18.5, 10), (19.5, 14.5), (18, 18.5),
                                           (15, 21.5), (12, 22.5), (9, 21.5), (6, 18.5), (4.5, 14.5),
                                           (6, 9.5), (8.5, 12.5), (9.5, 8), (11, 5)]),
                                fill=color, outline="", smooth=True)
            self.create_polygon(self._pts([(12, 12), (14.2, 15.2), (14.8, 18), (12, 20.5),
                                           (9.2, 18), (9.8, 15.2)]),
                                fill=bg, outline="", smooth=True)
        elif self.kind == "medical":
            self.create_rectangle(9 * k, 3 * k, 15 * k, 21 * k, fill=color, outline="")
            self.create_rectangle(3 * k, 9 * k, 21 * k, 15 * k, fill=color, outline="")
        elif self.kind == "alert":
            self.create_polygon(self._pts([(12, 2), (23, 21.5), (1, 21.5)]),
                                fill=color, outline="")
            self.create_rectangle(11 * k, 8 * k, 13 * k, 15 * k, fill=bg, outline="")
            self.create_rectangle(11 * k, 17 * k, 13 * k, 19 * k, fill=bg, outline="")
        elif self.kind == "radar":
            c = 12 * k
            self.create_oval(c - 2 * k, c - 2 * k, c + 2 * k, c + 2 * k, fill=color, outline="")
            for r in (5.5, 9, 12.5):
                self.create_arc(c - r * k, c - r * k, c + r * k, c + r * k, start=20, extent=50,
                                style="arc", outline=color, width=max(1, 1.6 * k))
                self.create_arc(c - r * k, c - r * k, c + r * k, c + r * k, start=200, extent=50,
                                style="arc", outline=color, width=max(1, 1.6 * k))
        elif self.kind == "document":
            self.create_rectangle(5 * k, 2 * k, 19 * k, 22 * k, outline=color, width=max(1, 1.6 * k))
            for y in (8, 12, 16):
                self.create_line(8 * k, y * k, 16 * k, y * k, fill=color, width=max(1, 1.6 * k))
        elif self.kind == "dot":
            self.create_oval(2 * k, 2 * k, 22 * k, 22 * k, fill=color, outline="")


def empty_state(parent, icon, title, hint, bg):
    box = ctk.CTkFrame(parent, fg_color="transparent")
    Icon(box, icon, size=48, color=FAINT, bg=bg).pack(pady=(40, 12))
    ctk.CTkLabel(box, text=title, text_color=TEXT, font=f(15, "bold")).pack()
    ctk.CTkLabel(box, text=hint, text_color=MUTED, font=f(12), justify="center",
                 wraplength=300).pack(pady=(4, 0))
    return box


# Confirmation dialog (for irreversible actions)
class ConfirmDialog(ctk.CTkToplevel):
    def __init__(self, master, title, message, confirm_text, colour):
        super().__init__(master)
        self.result = False
        self.title(title)
        self.configure(fg_color=PANEL)
        self.resizable(False, False)
        self.transient(master)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=24, pady=20)
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x")
        Icon(head, "alert", size=22, color="#b45309", bg=PANEL).pack(side="left")
        ctk.CTkLabel(head, text=title, text_color=TEXT, font=f(16, "bold")).pack(side="left", padx=10)
        ctk.CTkLabel(body, text=message, text_color=MUTED, font=f(13), justify="left",
                     wraplength=360, anchor="w").pack(fill="x", pady=(10, 18))

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x")
        ctk.CTkButton(btns, text=confirm_text, height=40, corner_radius=8, fg_color=colour[0],
                      hover_color=colour[1], text_color="white", font=f(13, "bold"),
                      command=self._yes).pack(side="right")
        ctk.CTkButton(btns, text="Cancel", height=40, corner_radius=8, fg_color=CARD,
                      hover_color=TRACK, text_color=TEXT, border_width=1, border_color=BORDER,
                      font=f(13, "bold"), command=self.destroy).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._yes())
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.after(10, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass

    def _yes(self):
        self.result = True
        self.destroy()

    @classmethod
    def ask(cls, master, *args):
        dialog = cls(master, *args)
        master.wait_window(dialog)
        return dialog.result


# Alert card in the feed
class ReportCard(ctk.CTkFrame):
    def __init__(self, parent, report, accent, on_click):
        super().__init__(parent, fg_color=CARD, corner_radius=10,
                         border_width=2, border_color=BORDER)
        self.report = report
        self.accent = accent
        self.selected = False

        ctk.CTkFrame(self, width=4, height=10, corner_radius=2,
                     fg_color=SEVERITY_BAR.get(report.severity, FAINT)).pack(
            side="left", fill="y", padx=(10, 0), pady=12)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")
        self.icon = Icon(top, TYPE_ICON.get(report.incident_type, "dot"), size=16,
                         color=TEXT, bg=CARD)
        self.icon.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(top, text=report.incident_type, text_color=TEXT,
                     font=f(12, "bold")).pack(side="left")
        ctk.CTkLabel(top, text=f"  {report.report_id}", text_color=FAINT,
                     font=f(11)).pack(side="left")
        ctk.CTkLabel(top, text=report.received_at[-8:], text_color=MUTED,
                     font=f(11)).pack(side="right")

        ctk.CTkLabel(body, text=report.location, text_color=TEXT, anchor="w",
                     font=f(15, "bold")).pack(fill="x", pady=(2, 6))

        badges = ctk.CTkFrame(body, fg_color="transparent")
        badges.pack(fill="x")
        pill(badges, report.severity, SEVERITY.get(report.severity, (MUTED, TRACK))).pack(side="left")
        self.status_pill = pill(badges, report.status, STATUS[report.status])
        self.status_pill.pack(side="left", padx=(6, 0))

        bind_tree(self, "<Button-1>", lambda _e: on_click(report.report_id))
        bind_tree(self, "<Enter>", self._hover_on)
        bind_tree(self, "<Leave>", self._hover_off)
        hand_cursor(self)

    def _hover_on(self, _e=None):
        if not self.selected:
            self.configure(border_color=BORDER_HOVER)

    def _hover_off(self, _e=None):
        x, y = self.winfo_pointerxy()
        under = self.winfo_containing(x, y)
        if under is not None and str(under).startswith(str(self)):
            return
        if not self.selected:
            self.configure(border_color=BORDER)

    def refresh_status(self):
        fg, bg = STATUS[self.report.status]
        self.status_pill.configure(text=f"  {self.report.status}  ", text_color=fg, fg_color=bg)

    def set_selected(self, selected):
        self.selected = selected
        bg = CARD_SELECTED if selected else CARD
        self.configure(border_color=self.accent if selected else BORDER, fg_color=bg)
        self.icon.configure(bg=bg)
        self.icon.draw(TEXT)


# Main dashboard
class ResponderDashboard:
    def __init__(self, master, subscriber: Subscriber, title: str, accent: str = ACCENT):
        _resolve_fonts(master)
        self.master = master
        self.sub = subscriber
        self.title = title
        self.accent = accent
        self.cards: dict[str, ReportCard] = {}
        self.order: list[str] = []  # newest first
        self.selected_id: str | None = None
        self.filter = "All"
        self._toast_job = None
        self._feedback_job = None

        master.title(f"RESPONDE · {title}")
        master.geometry("1200x760")
        master.minsize(1000, 640)
        master.configure(fg_color=BG)

        self._build_header()
        self._build_body()
        self._build_toast()
        self._bind_keys()

        self.sub.connect()
        self._refresh_connection()
        self._refresh_stats()
        self._show_details()
        self._poll()

    # Header
    def _build_header(self):
        header = ctk.CTkFrame(self.master, fg_color=HEADER, corner_radius=0, height=76)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkFrame(self.master, fg_color=self.accent, height=3, corner_radius=0).pack(fill="x")

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left", padx=22)
        ctk.CTkLabel(brand, text="R", width=40, height=40, corner_radius=10,
                     fg_color=PRIMARY, text_color="white",
                     font=f(20, "bold")).pack(side="left", pady=18)
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left", padx=12)
        ctk.CTkLabel(names, text="RESPONDE", text_color=HEADER_TEXT, font=f(18, "bold"),
                     anchor="w", height=22).pack(anchor="w")
        ctk.CTkLabel(names, text=self.title, text_color=HEADER_MUTED, font=f(12),
                     anchor="w", height=18).pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", padx=22)

        self.conn_btn = ctk.CTkButton(right, text="Go Offline", width=116, height=40,
                                      corner_radius=8, fg_color="#2c3a4d", hover_color="#3b4b61",
                                      border_width=1, border_color="#52627a",
                                      text_color=HEADER_TEXT, font=f(12, "bold"),
                                      command=self._toggle_connection)
        self.conn_btn.pack(side="right")
        self.conn_pill = ctk.CTkLabel(right, text="", corner_radius=14, height=28,
                                      font=f(12, "bold"))
        self.conn_pill.pack(side="right", padx=14)

        ctk.CTkFrame(right, fg_color=HEADER_LINE, width=1, height=36).pack(side="right", padx=8)

        self.stat_labels = {}
        for key, label, colour in (("completed", "COMPLETED", "#4ade80"),
                                   ("responding", "RESPONDING", "#fbbf24"),
                                   ("pending", "PENDING", "#f87171")):
            box = ctk.CTkFrame(right, fg_color="transparent")
            box.pack(side="right", padx=14)
            num = ctk.CTkLabel(box, text="0", text_color=colour, font=f(22, "bold"), height=26)
            num.pack()
            ctk.CTkLabel(box, text=label, text_color=HEADER_MUTED, font=f(11, "bold"),
                         height=14).pack()
            self.stat_labels[key] = num

    # Body: feed (left) + details/log (right)
    def _build_body(self):
        body = ctk.CTkFrame(self.master, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(18, 10))
        body.grid_columnconfigure(0, weight=2, uniform="cols")
        body.grid_columnconfigure(1, weight=3, uniform="cols")
        body.grid_rowconfigure(0, weight=1)

        # ---- feed ----
        feed = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=14,
                            border_width=1, border_color=BORDER)
        feed.grid(row=0, column=0, sticky="nsew", padx=(0, 9))

        feed_head = ctk.CTkFrame(feed, fg_color="transparent")
        feed_head.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(feed_head, text="Incoming Alerts", text_color=TEXT,
                     font=f(16, "bold")).pack(side="left")
        self.filter_btn = ctk.CTkSegmentedButton(
            feed_head, values=["All", "Active", "Done"], command=self._set_filter,
            font=f(12, "bold"), height=30, selected_color=CARD_SELECTED,
            selected_hover_color=CARD_SELECTED, unselected_color=TRACK,
            unselected_hover_color=BORDER, fg_color=TRACK, text_color=TEXT)
        self.filter_btn.set("All")
        self.filter_btn.pack(side="right")

        self.feed_list = ctk.CTkScrollableFrame(feed, fg_color="transparent",
                                                scrollbar_button_color=BORDER,
                                                scrollbar_button_hover_color=BORDER_HOVER)
        self.feed_list.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        topics = " and ".join(self.sub.topics)
        self.feed_empty = empty_state(
            self.feed_list, "radar", "No alerts yet",
            f"Reports sent to {topics} will appear here automatically. "
            "Keep this dashboard online.", PANEL)
        self.feed_empty.pack(fill="x")
        self.filter_empty = ctk.CTkLabel(self.feed_list, text="", text_color=MUTED, font=f(13))

        # ---- right side tabs ----
        self.tabs = ctk.CTkTabview(body, fg_color=PANEL, corner_radius=14,
                                   border_width=1, border_color=BORDER,
                                   segmented_button_selected_color=CARD_SELECTED,
                                   segmented_button_selected_hover_color=CARD_SELECTED,
                                   segmented_button_unselected_color=TRACK,
                                   segmented_button_unselected_hover_color=BORDER,
                                   segmented_button_fg_color=TRACK, text_color=TEXT)
        self.tabs.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        self.tabs.add("Report Details")
        self.tabs.add("Delivery Log")
        self.tabs._segmented_button.configure(font=f(12, "bold"), height=30)

        self._build_details(self.tabs.tab("Report Details"))
        self._build_log(self.tabs.tab("Delivery Log"))

        # ---- keyboard hint bar ----
        ctk.CTkLabel(self.master, text="Keyboard:   ↑ ↓  select alert     1  Received     "
                                       "2  Responding     3  Completed     Esc  close popup",
                     text_color=TEXT, font=f(11), anchor="w").pack(fill="x", padx=22, pady=(0, 8))

    def _build_details(self, parent):
        self.detail_empty = empty_state(parent, "document", "No alert selected",
                                        "Click an alert on the left (or press ↓) to see its "
                                        "details and update its status.", PANEL)
        self.detail = ctk.CTkFrame(parent, fg_color="transparent")

        d = self.detail
        type_row = ctk.CTkFrame(d, fg_color="transparent")
        type_row.pack(fill="x", padx=14, pady=(10, 0))
        self.d_icon = Icon(type_row, "dot", size=16, color=MUTED, bg=PANEL)
        self.d_icon.pack(side="left", padx=(0, 6))
        self.d_type = ctk.CTkLabel(type_row, text="", text_color=MUTED, font=f(12, "bold"),
                                   anchor="w")
        self.d_type.pack(side="left")
        self.d_location = ctk.CTkLabel(d, text="", text_color=TEXT, font=f(26, "bold"), anchor="w")
        self.d_location.pack(fill="x", padx=14)

        badges = ctk.CTkFrame(d, fg_color="transparent")
        badges.pack(fill="x", padx=14, pady=(6, 12))
        self.d_sev = pill(badges, "", (MUTED, CARD))
        self.d_sev.pack(side="left")
        self.d_status = pill(badges, "", (MUTED, CARD))
        self.d_status.pack(side="left", padx=6)

        desc_box = ctk.CTkFrame(d, fg_color=CARD, corner_radius=10)
        desc_box.pack(fill="x", padx=14)
        ctk.CTkLabel(desc_box, text="DESCRIPTION", text_color=FAINT, font=f(11, "bold"),
                     anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        self.d_desc = ctk.CTkLabel(desc_box, text="", text_color=TEXT, font=f(14),
                                   anchor="w", justify="left", wraplength=540)
        self.d_desc.pack(fill="x", padx=14, pady=(2, 12))

        meta = ctk.CTkFrame(d, fg_color="transparent")
        meta.pack(fill="x", padx=14, pady=12)
        self.d_meta = {}
        for i, name in enumerate(("Source", "Topic", "Sent", "Received")):
            meta.grid_columnconfigure(i % 2, weight=1)
            cell = ctk.CTkFrame(meta, fg_color="transparent")
            cell.grid(row=i // 2, column=i % 2, sticky="w", pady=4)
            ctk.CTkLabel(cell, text=name.upper(), text_color=FAINT, font=f(11, "bold"),
                         anchor="w", height=14).pack(anchor="w")
            val = ctk.CTkLabel(cell, text="-", text_color=TEXT, font=f(13), anchor="w", height=20)
            val.pack(anchor="w")
            self.d_meta[name] = val

        # progress stepper
        ctk.CTkLabel(d, text="RESPONSE PROGRESS", text_color=FAINT, font=f(11, "bold"),
                     anchor="w").pack(fill="x", padx=14, pady=(4, 4))
        stepper = ctk.CTkFrame(d, fg_color=CARD, corner_radius=10)
        stepper.pack(fill="x", padx=14)
        self.step_dots, self.step_lines, self.step_names, self.step_times = [], [], [], []
        for i, status in enumerate(STATUS_ORDER):
            if i:
                stepper.grid_columnconfigure(i * 2 - 1, weight=1)
                line = ctk.CTkFrame(stepper, height=3, fg_color=BORDER, corner_radius=2)
                line.grid(row=0, column=i * 2 - 1, sticky="ew", pady=(20, 0))
                self.step_lines.append(line)
            cell = ctk.CTkFrame(stepper, fg_color="transparent")
            cell.grid(row=0, column=i * 2, padx=10, pady=10)
            dot = tk.Canvas(cell, width=32, height=32, bg=CARD, highlightthickness=0)
            dot.create_oval(2, 2, 30, 30, fill=BORDER, outline="", tags="circle")
            dot.create_text(16, 16, text=str(i + 1), fill=MUTED,
                            font=(FONT, 11, "bold"), tags="label")
            dot.pack()
            name = ctk.CTkLabel(cell, text=status.title(), text_color=MUTED, font=f(12, "bold"),
                                height=16)
            name.pack(pady=(4, 0))
            t = ctk.CTkLabel(cell, text="", text_color=FAINT, font=f(11), height=14)
            t.pack()
            self.step_dots.append(dot)
            self.step_names.append(name)
            self.step_times.append(t)

        # action buttons
        actions = ctk.CTkFrame(d, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(16, 4))
        self.status_buttons = {}
        for i, status in enumerate((STATUS_RECEIVED, STATUS_RESPONDING, STATUS_COMPLETED)):
            actions.grid_columnconfigure(i, weight=1, uniform="btn")
            colour, hover = STATUS_BUTTON[status]
            b = ctk.CTkButton(actions, text=f"{status}   {SHORTCUT[status]}", height=46,
                              corner_radius=10, fg_color=colour, hover_color=hover,
                              font=f(13, "bold"), text_color="white",
                              text_color_disabled=DISABLED_TEXT,
                              command=lambda s=status: self._request_status(s))
            b.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == 2 else 5))
            self.status_buttons[status] = b

        self.feedback = ctk.CTkLabel(d, text="", text_color=STATUS[STATUS_COMPLETED][0],
                                     font=f(12, "bold"), anchor="w", height=20)
        self.feedback.pack(fill="x", padx=16)

    def _build_log(self, parent):
        self.log = ctk.CTkTextbox(parent, fg_color=CARD, text_color=TEXT, corner_radius=10,
                                  font=ctk.CTkFont(family=MONO, size=12), wrap="none",
                                  border_width=1, border_color=BORDER)
        self.log.pack(fill="both", expand=True, padx=6, pady=6)
        colours = {"ACK": "#166534", "DELIVERED": "#1d4ed8", "NACK": "#b91c1c",
                   "ACK FAILED": "#b91c1c", "STATUS FAILED": "#b91c1c",
                   "STATUS": "#92400e", "DUPLICATE": MUTED, "CONNECTED": "#166534",
                   "DISCONNECTED": "#b91c1c", "REGISTERED": MUTED}
        for tag, colour in colours.items():
            self.log.tag_config(tag, foreground=colour)
        self.log.tag_config("time", foreground=FAINT)
        self.log.configure(state="disabled")

    # New-alert popup
    def _build_toast(self):
        bg = "#f6d3d3"
        self.toast = ctk.CTkFrame(self.master, fg_color=bg, corner_radius=12,
                                  border_width=2, border_color=PRIMARY)
        inner = ctk.CTkFrame(self.toast, fg_color="transparent")
        inner.pack(padx=(16, 8), pady=8)
        Icon(inner, "alert", size=20, color="#b91c1c", bg=bg).pack(side="left")
        ctk.CTkLabel(inner, text="NEW ALERT", text_color="#b91c1c",
                     font=f(13, "bold")).pack(side="left", padx=(8, 0))
        self.toast_text = ctk.CTkLabel(inner, text="", text_color=TEXT, font=f(13))
        self.toast_text.pack(side="left", padx=(14, 6))
        ctk.CTkButton(inner, text="✕", width=30, height=30, corner_radius=6,
                      fg_color="transparent", hover_color="#ebbcbc", text_color=TEXT,
                      font=f(13, "bold"), command=self._hide_toast).pack(side="left")

    def _show_toast(self, r):
        self.toast_text.configure(text=f"{r.incident_type}  ·  {r.location}  ·  {r.severity}")
        self.toast.place(relx=1.0, x=-26, y=94, anchor="ne")
        self.toast.lift()
        if not REDUCE_MOTION:
            self._pulse(6)
        if self._toast_job:
            self.master.after_cancel(self._toast_job)
        self._toast_job = self.master.after(TOAST_MS, self._hide_toast)
        try:
            self.master.bell()
        except Exception:
            pass

    def _pulse(self, n):
        if n <= 0 or not self.toast.winfo_ismapped():
            self.toast.configure(border_color=PRIMARY)
            return
        self.toast.configure(border_color=PRIMARY if n % 2 else "#f19a9a")
        self.master.after(300, self._pulse, n - 1)

    def _hide_toast(self):
        self.toast.place_forget()
        self._toast_job = None

    # Keyboard
    def _bind_keys(self):
        m = self.master
        m.bind("<Down>", lambda _e: self._move_selection(1))
        m.bind("<Up>", lambda _e: self._move_selection(-1))
        for status, key in SHORTCUT.items():
            m.bind(key, lambda _e, s=status: self._request_status(s))
        m.bind("<Escape>", lambda _e: self._hide_toast())

    def _move_selection(self, step):
        visible = [rid for rid in self.order if self._visible(self.cards[rid].report)]
        if not visible:
            return
        if self.selected_id not in visible:
            self._select(visible[0])
            return
        i = max(0, min(len(visible) - 1, visible.index(self.selected_id) + step))
        self._select(visible[i])

    # Polling loop (Tk main thread)
    def _poll(self):
        events = self.sub.drain_new_events()
        if events:
            self.log.configure(state="normal")
            for e in events:
                self.log.insert("end", e.time[-8:] + "  ", "time")
                self.log.insert("end", f"{e.event:<13}", e.event)
                rid = f"[{e.report_id}] " if e.report_id else ""
                self.log.insert("end", f"{rid}{e.detail}\n")
            self.log.see("end")
            self.log.configure(state="disabled")

        new = self.sub.drain_new_reports()
        for r in new:
            self._add_card(r)
        if new:
            self._show_toast(new[-1])
            self._refresh_stats()
            if self.selected_id is None:
                self._select(new[-1].report_id)

        self.master.after(POLL_MS, self._poll)

    # Feed
    def _add_card(self, r):
        card = ReportCard(self.feed_list, r, self.accent, self._select)
        self.cards[r.report_id] = card
        self.order.insert(0, r.report_id)
        self._repack_feed()

    def _visible(self, r):
        if self.filter == "Active":
            return r.status != STATUS_COMPLETED
        if self.filter == "Done":
            return r.status == STATUS_COMPLETED
        return True

    def _repack_feed(self):
        self.feed_empty.pack_forget()
        self.filter_empty.pack_forget()
        for rid in self.order:
            self.cards[rid].pack_forget()
        shown = 0
        for rid in self.order:
            card = self.cards[rid]
            if self._visible(card.report):
                card.pack(fill="x", padx=6, pady=5)
                shown += 1
        if not self.order:
            self.feed_empty.pack(fill="x")
        elif shown == 0:
            text = ("No completed alerts yet." if self.filter == "Done"
                    else "All alerts are completed. Nice work.")
            self.filter_empty.configure(text=text)
            self.filter_empty.pack(fill="x", pady=40)

    def _set_filter(self, value):
        self.filter = value
        self._repack_feed()

    def _select(self, report_id):
        if self.selected_id in self.cards:
            self.cards[self.selected_id].set_selected(False)
        self.selected_id = report_id
        self.cards[report_id].set_selected(True)
        self.tabs.set("Report Details")
        self.feedback.configure(text="")
        self._show_details()

    # Details
    def _show_details(self):
        r = self.sub.reports.get(self.selected_id) if self.selected_id else None
        if r is None:
            self.detail.pack_forget()
            self.detail_empty.pack(expand=True)
            return
        self.detail_empty.pack_forget()
        self.detail.pack(fill="both", expand=True)

        self.d_icon.kind = TYPE_ICON.get(r.incident_type, "dot")
        self.d_icon.draw(MUTED)
        self.d_type.configure(text=f"{r.incident_type} EMERGENCY  ·  {r.report_id}")
        self.d_location.configure(text=r.location)
        sfg, sbg = SEVERITY.get(r.severity, (MUTED, CARD))
        self.d_sev.configure(text=f"  {r.severity}  ", text_color=sfg, fg_color=sbg)
        tfg, tbg = STATUS[r.status]
        self.d_status.configure(text=f"  {r.status}  ", text_color=tfg, fg_color=tbg)
        self.d_desc.configure(text=r.description or "No description provided.")
        self.d_meta["Source"].configure(text=r.source or "-")
        self.d_meta["Topic"].configure(text=r.topic)
        self.d_meta["Sent"].configure(text=r.sent_at or "-")
        self.d_meta["Received"].configure(text=r.received_at)

        current = STATUS_ORDER.index(r.status)
        times = {s: t[-8:] for t, s in r.status_history}
        for i, status in enumerate(STATUS_ORDER):
            done = i <= current
            colour = STEP_DOT[status] if done else BORDER
            self.step_dots[i].itemconfigure("circle", fill=colour)
            self.step_dots[i].itemconfigure("label", text="✓" if done else str(i + 1),
                                            fill="white" if done else MUTED)
            self.step_names[i].configure(text_color=TEXT if done else MUTED)
            self.step_times[i].configure(text=times.get(status, ""))
            if i:
                self.step_lines[i - 1].configure(fg_color=colour if done else BORDER)

        for status, btn in self.status_buttons.items():
            enabled = self.sub.can_set_status(r.report_id, status)
            colour, _ = STATUS_BUTTON[status]
            btn.configure(state="normal" if enabled else "disabled",
                          fg_color=colour if enabled else DISABLED_BG)

    def _request_status(self, status):
        """COMPLETED cannot be undone, so it asks for confirmation first."""
        if not self.selected_id or not self.sub.can_set_status(self.selected_id, status):
            return
        if status == STATUS_COMPLETED:
            r = self.sub.reports[self.selected_id]
            ok = ConfirmDialog.ask(
                self.master, "Mark as completed?",
                f"{r.incident_type} at {r.location} ({r.report_id}) will be closed. "
                "This can't be undone.",
                "Mark Completed", STATUS_BUTTON[STATUS_COMPLETED])
            if not ok:
                return
        self._apply_status(status)

    def _apply_status(self, status):
        if self.selected_id and self.sub.set_status(self.selected_id, status):
            self.cards[self.selected_id].refresh_status()
            self._show_details()
            self._refresh_stats()
            self._repack_feed()
            self._flash_feedback(f"✓  {self.selected_id} marked as {status.title()}")
        else:
            self._flash_feedback("Could not update status. Check the delivery log.", error=True)

    def _flash_feedback(self, text, error=False):
        self.feedback.configure(text=text, text_color="#b91c1c" if error
                                else STATUS[STATUS_COMPLETED][0])
        if self._feedback_job:
            self.master.after_cancel(self._feedback_job)
        self._feedback_job = self.master.after(
            FEEDBACK_MS, lambda: self.feedback.configure(text=""))

    def _refresh_stats(self):
        counts = {"pending": 0, "responding": 0, "completed": 0}
        for r in self.sub.reports.values():
            if r.status in (STATUS_NEW, STATUS_RECEIVED):
                counts["pending"] += 1
            elif r.status == STATUS_RESPONDING:
                counts["responding"] += 1
            else:
                counts["completed"] += 1
        for k, v in counts.items():
            self.stat_labels[k].configure(text=str(v))

    # Connection
    def _toggle_connection(self):
        if self.sub.connected:
            self.sub.disconnect()
        else:
            self.sub.connect()
        self._refresh_connection()

    def _refresh_connection(self):
        if self.sub.connected:
            self.conn_pill.configure(text="  ●  ONLINE  ", text_color="#4ade80", fg_color="#1f3d33")
            self.conn_btn.configure(text="Go Offline")
        else:
            self.conn_pill.configure(text="  ●  OFFLINE  ", text_color="#fca5a5", fg_color="#462a32")
            self.conn_btn.configure(text="Reconnect")