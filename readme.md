# RESPONDE

RESPONDE is an emergency-reporting system with publisher and responder
dashboards, topic-based routing, persistent SQLite queues, acknowledgments,
redelivery, and response status updates.

## Requirements

- Python 3.10 or newer

## Installation

Install the required dependency on each computer that will run a dashboard:

```powershell
py -m pip install -r requirements.txt
```

## Run everything on one computer

From the project directory:

```powershell
py main.py
```

This opens the Fire Station, Ambulance Team, Command Center, 911 Operator,
and Barangay Hotline dashboards connected to a local broker.

## Run on multiple computers on the same LAN

The broker host owns the SQLite database. Other computers connect to it over
the local network; do not copy or share the database file between computers.

1. On the broker computer, start the broker:

   ```powershell
   py main.py --server
   ```

   The broker listens on all network interfaces at port `8000`.

2. Find the broker computer's LAN IPv4 address by running `ipconfig` there.
   Use its IPv4 address (for example, `192.168.1.25`), not `127.0.0.1`.

3. If Windows Firewall prompts you, allow Python on **Private networks**.
   If it does not prompt, create an inbound TCP rule for port 8000 on the
   Private profile. In an elevated PowerShell window:

   ```powershell
   New-NetFirewallRule -DisplayName "RESPONDE broker" -Direction Inbound `
     -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
   ```

4. On each dashboard computer, start the role or roles for that computer,
   replacing the example address with the broker computer's LAN IP:

   ```powershell
   py main.py --connect http://192.168.1.25:8000 --role operator
   ```

   Available roles:

   | Role | Dashboard |
   | --- | --- |
   | `operator` | 911 Operator |
   | `barangay` | Barangay Hotline |
   | `fire` | Fire Station |
   | `ambulance` | Ambulance Team |
   | `command` | Command Center |

   You can open multiple roles in one process by repeating `--role`, for
   example `--role fire --role command`.

The broker must remain running while clients are connected. Responders poll
for reports and acknowledge them automatically; if a responder is offline,
reports remain queued and are delivered when it reconnects. Reports and status
updates are stored on the broker computer.

This connection is intended for a trusted private LAN. It does not provide
authentication or encryption; do not expose port 8000 to the public internet
or forward it from your router.

## Send a report

1. Open the 911 Operator or Barangay Hotline dashboard.
2. Choose **FIRE** or **MEDICAL**.
3. Enter a location and severity.
4. Optionally enter an incident description.
5. Select **SEND REPORT**.

Routing rules:

- FIRE reports go to the Fire Station and Command Center.
- MEDICAL reports go to the Ambulance Team and Command Center.
- Subscribers receive only reports for their configured topics.

## Test offline redelivery

1. Start the application or connect the Ambulance dashboard to the broker.
2. In the Ambulance window, select **Go Offline**.
3. Send a MEDICAL report from the 911 Operator dashboard.
4. Confirm that the Ambulance report is listed as **QUEUED**.
5. Select **Reconnect** in the Ambulance window.
6. The queued report is delivered and the publisher receipt becomes
   **Acknowledged**.

## Update response status

In a responder dashboard:

1. Open a delivered report.
2. Move it through **Received**, **Responding**, and **Completed**.
3. Status changes can only move forward.

Responder dashboards reload their assigned reports and saved response statuses
from the broker when they connect. Status changes are shared across responders,
including the Command Center. Publisher dashboards reload their own sent-report
history and saved delivery receipts when they connect.

## Run tests

```powershell
py -m unittest discover -s tests -v
```

The suite covers publisher validation, topic routing, offline redelivery,
acknowledgments, duplicate delivery, queue persistence, response statuses, and
the multi-device broker transport.
