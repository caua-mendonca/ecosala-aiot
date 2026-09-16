from __future__ import annotations

import socket

from app.domain.entities.evaluated_reading import EvaluatedReading


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class FakeReadingRepository:
    def __init__(self) -> None:
        self.saved: list[EvaluatedReading] = []

    def save(self, evaluated_reading: EvaluatedReading) -> None:
        self.saved.append(evaluated_reading)

    def get_latest(self, room_id: str | None = None) -> list[EvaluatedReading]:
        return []

    def get_history(
        self, device_id: str, start: str, stop: str, window: str
    ) -> list[EvaluatedReading]:
        return []
