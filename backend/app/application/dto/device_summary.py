from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DeviceSummaryDTO:
    """Representacao de um dispositivo conhecido, pronta para a presentation."""

    device_id: str
    room_id: str
    online: bool
    last_seen: datetime | None
