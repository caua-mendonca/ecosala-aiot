from __future__ import annotations

from datetime import UTC, datetime

from fakes import FakeReadingRepository

from app.application.dto.incoming_reading import IncomingReadingDTO
from app.application.use_cases.ingest_reading import IngestReading
from app.domain.services.comfort_evaluator import ComfortEvaluator
from app.domain.value_objects.comfort_status import ComfortStatus
from app.domain.value_objects.comfort_thresholds import ComfortThresholds


def make_thresholds() -> ComfortThresholds:
    return ComfortThresholds(
        temperature_min_c=20.0,
        temperature_max_c=26.0,
        humidity_min_percent=40.0,
        humidity_max_percent=60.0,
        luminosity_min_lux=300.0,
        temperature_critical_margin_c=4.0,
        humidity_critical_margin_percent=15.0,
        luminosity_critical_margin_lux=150.0,
    )


def test_ingest_reading_saves_evaluated_reading_and_returns_status() -> None:
    repository = FakeReadingRepository()
    evaluator = ComfortEvaluator(make_thresholds())
    use_case = IngestReading(repository=repository, evaluator=evaluator)

    dto = IncomingReadingDTO(
        device_id="esp32-sala-101",
        room_id="sala-101",
        timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        temperature=23.0,
        humidity=50.0,
        luminosity=400.0,
    )

    status = use_case.execute(dto)

    assert status == ComfortStatus.OK
    assert len(repository.saved) == 1
    assert repository.saved[0].reading.device_id == "esp32-sala-101"
    assert repository.saved[0].comfort_status == ComfortStatus.OK


def test_ingest_reading_classifies_critical_reading() -> None:
    repository = FakeReadingRepository()
    evaluator = ComfortEvaluator(make_thresholds())
    use_case = IngestReading(repository=repository, evaluator=evaluator)

    dto = IncomingReadingDTO(
        device_id="esp32-sala-101",
        room_id="sala-101",
        timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        temperature=32.0,
        humidity=50.0,
        luminosity=400.0,
    )

    status = use_case.execute(dto)

    assert status == ComfortStatus.CRITICO
    assert repository.saved[0].comfort_status == ComfortStatus.CRITICO
