from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IncomingReadingDTO:
    """Leitura ja validada, pronta para ser processada pelo caso de uso IngestReading."""

    device_id: str
    room_id: str
    timestamp: datetime
    temperature: float
    humidity: float
    luminosity: float
