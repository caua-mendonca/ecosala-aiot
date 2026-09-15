from __future__ import annotations

from app.application.dto.reading_summary import ReadingSummaryDTO
from app.domain.ports.reading_repository import ReadingRepository


class GetLatestReadings:
    """Caso de uso: retorna a ultima leitura conhecida de cada dispositivo."""

    def __init__(self, repository: ReadingRepository) -> None:
        self._repository = repository

    def execute(self, room_id: str | None = None) -> list[ReadingSummaryDTO]:
        evaluated_readings = self._repository.get_latest(room_id)
        return [ReadingSummaryDTO.from_evaluated_reading(item) for item in evaluated_readings]
