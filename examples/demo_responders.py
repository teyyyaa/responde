"""
Demo: all three responder dashboards plus a test publisher, using the mock broker.

Run from the project root:
    python -m examples.demo_responders
"""

import customtkinter as ctk

from clients.messages import INCIDENT_TYPES, SEVERITIES, make_report, topic_for
from clients.mock_broker import MockBroker
from ui import ambulance_dashboard, command_center_dashboard, fire_station_dashboard
from ui import responder_dashboard as theme


def open_test_publisher(master, broker):
    """Minimal publisher window for testing until the operator dashboard is connected."""
    theme._resolve_fonts(master)
    f = theme.f
    win = ctk.CTkToplevel(master)
    win.title("RESPONDE · Test Publisher")
    win.geometry("400x500")
    win.configure(fg_color=theme.BG)

    card = ctk.CTkFrame(win, fg_color=theme.PANEL, corner_radius=14,
                        border_width=1, border_color=theme.BORDER)
    card.pack(fill="both", expand=True, padx=16, pady=16)
    ctk.CTkLabel(card, text="Report Emergency", text_color=theme.TEXT, font=f(18, "bold"),
                 anchor="w").pack(fill="x", padx=18, pady=(16, 10))

    def field(label, widget):
        ctk.CTkLabel(card, text=label.upper(), text_color=theme.FAINT, font=f(11, "bold"),
                     anchor="w").pack(fill="x", padx=18, pady=(6, 2))
        widget.pack(fill="x", padx=18)
        return widget

    opt = dict(height=38, corner_radius=8, fg_color=theme.CARD, button_color=theme.BORDER,
               button_hover_color=theme.BORDER_HOVER, dropdown_fg_color=theme.PANEL,
               text_color=theme.TEXT, dropdown_text_color=theme.TEXT,
               dropdown_hover_color=theme.TRACK, font=f(13))
    ent = dict(height=38, corner_radius=8, fg_color=theme.CARD, border_color=theme.BORDER,
               text_color=theme.TEXT, font=f(13))

    type_box = field("Type", ctk.CTkOptionMenu(card, values=list(INCIDENT_TYPES), **opt))
    loc = field("Location", ctk.CTkEntry(card, **ent))
    loc.insert(0, "Brgy. Tabuc Suba")
    sev = field("Priority", ctk.CTkOptionMenu(card, values=list(reversed(SEVERITIES)), **opt))
    desc = field("Description", ctk.CTkEntry(card, **ent))
    desc.insert(0, "House fire")
    result = ctk.CTkLabel(card, text="", text_color=theme.TEXT, font=f(12),
                          justify="left", anchor="w")

    def send():
        if not loc.get().strip():
            result.configure(text="Location is required.", text_color="#b91c1c")
            return
        report = make_report(type_box.get(), loc.get(), sev.get(), desc.get(), "Test Publisher")
        delivered, queued = broker.publish(topic_for(report), report)
        lines = [f"{report['report_id']} sent to {topic_for(report)}"]
        lines += [f"✓ {n}" for n in delivered] + [f"Queued (offline): {n}" for n in queued]
        result.configure(text="\n".join(lines), text_color=theme.TEXT)

    ctk.CTkButton(card, text="SEND REPORT", height=46, corner_radius=10,
                  fg_color=theme.PRIMARY, hover_color="#b91c1c", text_color="white",
                  font=f(14, "bold"), command=send).pack(fill="x", padx=18, pady=(16, 8))
    result.pack(fill="x", padx=18)
    return win


def main():
    broker = MockBroker()
    root = ctk.CTk()
    root.withdraw()

    for i, module in enumerate((fire_station_dashboard, ambulance_dashboard,
                                command_center_dashboard)):
        win = ctk.CTkToplevel(root)
        module.open_dashboard(win, broker)
        win.geometry(f"1200x760+{40 + i * 40}+{40 + i * 40}")
        win.protocol("WM_DELETE_WINDOW", root.destroy)

    pub = open_test_publisher(root, broker)
    pub.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
    