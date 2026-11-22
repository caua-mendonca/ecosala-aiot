from __future__ import annotations

from app.application.dto.incoming_reading import IncomingReadingDTO
from app.domain.entities.evaluated_reading import EvaluatedReading
from app.domain.entities.reading import Reading
from app.domain.ports.reading_repository import ReadingRepository
from app.domain.services.comfort_evaluator import ComfortEvaluator
from app.domain.value_objects.comfort_status import ComfortStatus


class IngestReading:
    def __init__(self, repository: ReadingRepository, evaluator: ComfortEvaluator) -> None:
        self._repository = repository
        self._evaluator = evaluator

    def execute(self, dto: IncomingReadingDTO) -> ComfortStatus:
        reading = Reading(
            device_id=dto.device_id,
            room_id=dto.room_id,
            timestamp=dto.timestamp,
            temperature=dto.temperature,
            humidity=dto.humidity,
            luminosity=dto.luminosity,
        )
        comfort_status = self._evaluator.evaluate(reading)
        self._repository.save(EvaluatedReading(reading=reading, comfort_status=comfort_status))
        return comfort_status
