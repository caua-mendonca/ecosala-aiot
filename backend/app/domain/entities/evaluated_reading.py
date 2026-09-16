from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.reading import Reading
from app.domain.value_objects.comfort_status import ComfortStatus


@dataclass(frozen=True)
class EvaluatedReading:
    reading: Reading
    comfort_status: ComfortStatus
