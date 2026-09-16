from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Reading:
    device_id: str
    room_id: str
    timestamp: datetime
    temperature: float
    humidity: float
    luminosity: float
