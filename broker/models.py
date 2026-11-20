# Broker: accepts connections, routes messages by topic, and stores persistent queues

#   Models:
#   Report - id, incident type, details like address and severity
#   Subscription - 
#   Delivery
#   IncidentType (Fire / Medical / Police / Other)

from dataclasses import dataclass
from enum import Enum

class IncidentType(Enum):
    FIRE = "emergency/fire"
    MEDICAL = "emergency/medical"
    POLICE = "emergency/police"
    OTHER = "emergency/other"

@dataclass
class Report:
    report_id: int
    topic: IncidentType
    location: str
    description: str
    priority: str

@dataclass
class Subscriber:
    name: str
    topics: list