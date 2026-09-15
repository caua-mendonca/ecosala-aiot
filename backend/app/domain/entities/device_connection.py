from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DeviceConnection:
    """Status de conectividade conhecido de um dispositivo (via topico de status/LWT)."""

    device_id: str
    room_id: str
    online: bool
    last_seen: datetime | None
