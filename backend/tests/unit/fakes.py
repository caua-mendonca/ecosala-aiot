from __future__ import annotations

from app.domain.entities.device_connection import DeviceConnection
from app.domain.entities.evaluated_reading import EvaluatedReading


class FakeReadingRepository:
    """Implementacao em memoria de ReadingRepository, para testes de casos de uso."""

    def __init__(self) -> None:
        self.saved: list[EvaluatedReading] = []
        self.latest_by_room: dict[str | None, list[EvaluatedReading]] = {}
        self.history: list[EvaluatedReading] = []

    def save(self, evaluated_reading: EvaluatedReading) -> None:
        self.saved.append(evaluated_reading)

    def get_latest(self, room_id: str | None = None) -> list[EvaluatedReading]:
        return self.latest_by_room.get(room_id, [])

    def get_history(
        self, device_id: str, start: str, stop: str, window: str
    ) -> list[EvaluatedReading]:
        return [item for item in self.history if item.reading.device_id == device_id]


class FakeMessageSubscriber:
    """Implementacao em memoria de MessageSubscriber, para testes de casos de uso."""

    def __init__(self, devices: list[DeviceConnection] | None = None) -> None:
        self.devices = devices or []
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def get_known_devices(self) -> list[DeviceConnection]:
        return self.devices
