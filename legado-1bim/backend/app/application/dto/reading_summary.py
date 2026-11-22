from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.evaluated_reading import EvaluatedReading
from app.domain.value_objects.comfort_status import ComfortStatus


@dataclass(frozen=True)
class ReadingSummaryDTO:
    device_id: str
    room_id: str
    timestamp: datetime
    temperature: float
    humidity: float
    luminosity: float
    comfort_status: ComfortStatus

    @classmethod
    def from_evaluated_reading(cls, evaluated_reading: EvaluatedReading) -> ReadingSummaryDTO:
        reading = evaluated_reading.reading
        return cls(
            device_id=reading.device_id,
            room_id=reading.room_id,
            timestamp=reading.timestamp,
            temperature=reading.temperature,
            humidity=reading.humidity,
            luminosity=reading.luminosity,
            comfort_status=evaluated_reading.comfort_status,
        )
