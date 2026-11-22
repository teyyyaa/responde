# RESPONDE

RESPONDE is an emergency-reporting demo with publisher dashboards, responder
dashboards, topic-based routing, persistent SQLite queues, acknowledgments,
redelivery, and response status updates.

## Requirements

- Python 3.10 or newer
- CustomTkinter

Install CustomTkinter from the project directory:

```powershell
py -m pip install customtkinter
```

## Run the complete application

From the project directory:

```powershell
py main.py
```

This opens five windows:

1. Fire Station
2. Ambulance Team
3. Command Center
4. 911 Operator
5. Barangay Hotline

The responder windows register as subscribers. The publisher windows send reports.

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

1. Start the application.
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

Status updates are persisted with the report and subscriber.

## Run the HTTP API

```powershell
py main.py --api
```

The server listens at `http://127.0.0.1:8000`.

### Publish a report

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/publish" `
  -ContentType "application/json" `
  -Body '{"report_id":"R-DEMO","incident_type":"FIRE","location":"Jaro","severity":"HIGH","description":"Building fire","source":"API"}'
```

### Subscribe an HTTP subscriber

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/subscribe" `
  -ContentType "application/json" `
  -Body '{"subscriber_id":"fire_api","name":"Fire API","topics":["emergency/fire"],"online":true}'
```

### Update a response

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/respond" `
  -ContentType "application/json" `
  -Body '{"subscriber_id":"fire_api","report_id":"R-DEMO","status":"COMPLETED"}'
```

### Read persisted reports

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/reports"
```

## Run tests

```powershell
py -m unittest discover -s tests -v
```

The suite covers publisher validation, topic routing, offline redelivery,
acknowledgments, duplicate delivery, queue persistence, and response statuses.