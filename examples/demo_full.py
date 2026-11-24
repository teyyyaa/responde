"""
Demo: both publisher dashboards (911 Operator, Barangay Hotline) and all three
responder dashboards (Fire Station, Ambulance, Command Center) on one broker.

Run from the project root:
    python -m examples.demo_full

Try the offline scenario: click "Go Offline" on the Ambulance dashboard, send a
MEDICAL report from the 911 Operator, then click "Reconnect". The operator sees
the Ambulance go from "queued" to "Acknowledged".

Uses the persistent real broker.
"""

import customtkinter as ctk

from broker.broker import Broker
from ui import (
    ambulance_dashboard,
    barangay_dashboard,
    command_center_dashboard,
    fire_station_dashboard,
    operator_dashboard,
)


def main(broker=None, roles=None):
    broker = broker or Broker()
    root = ctk.CTk()
    root.withdraw()

    available = {
        "fire": fire_station_dashboard,
        "ambulance": ambulance_dashboard,
        "command": command_center_dashboard,
        "operator": operator_dashboard,
        "barangay": barangay_dashboard,
    }
    selected = set(roles or available)
    modules = [module for role, module in available.items() if role in selected]
    for i, module in enumerate(modules):
        win = ctk.CTkToplevel(root)
        module.open_dashboard(win, broker)
        win.geometry(f"1200x760+{40 + i * 40}+{40 + i * 40}")
        win.protocol("WM_DELETE_WINDOW", root.destroy)

    root.mainloop()


if __name__ == "__main__":
    main()
