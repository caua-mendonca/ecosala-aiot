from __future__ import annotations

from app.application.dto.reading_summary import ReadingSummaryDTO
from app.domain.ports.reading_repository import ReadingRepository


class GetReadingHistory:
    """Caso de uso: retorna o historico agregado de leituras de um dispositivo."""

    def __init__(self, repository: ReadingRepository) -> None:
        self._repository = repository

    def execute(
        self, device_id: str, start: str, stop: str, window: str
    ) -> list[ReadingSummaryDTO]:
        evaluated_readings = self._repository.get_history(device_id, start, stop, window)
        return [ReadingSummaryDTO.from_evaluated_reading(item) for item in evaluated_readings]
