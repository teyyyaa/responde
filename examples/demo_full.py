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


def main():
    broker = Broker()
    root = ctk.CTk()
    root.withdraw()

    # Responders first, so they are registered before the first report.
    modules = (fire_station_dashboard, ambulance_dashboard, command_center_dashboard,
               operator_dashboard, barangay_dashboard)
    for i, module in enumerate(modules):
        win = ctk.CTkToplevel(root)
        module.open_dashboard(win, broker)
        win.geometry(f"1200x760+{40 + i * 40}+{40 + i * 40}")
        win.protocol("WM_DELETE_WINDOW", root.destroy)

    root.mainloop()


if __name__ == "__main__":
    main()
