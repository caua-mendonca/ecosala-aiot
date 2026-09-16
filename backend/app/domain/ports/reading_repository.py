from __future__ import annotations

from typing import Protocol

from app.domain.entities.evaluated_reading import EvaluatedReading


class ReadingRepository(Protocol):
    def save(self, evaluated_reading: EvaluatedReading) -> None: ...

    def get_latest(self, room_id: str | None = None) -> list[EvaluatedReading]: ...

    def get_history(
        self, device_id: str, start: str, stop: str, window: str
    ) -> list[EvaluatedReading]: ...
