from __future__ import annotations

from datetime import UTC, datetime

from fakes import FakeReadingRepository

from app.application.use_cases.get_reading_history import GetReadingHistory
from app.domain.entities.evaluated_reading import EvaluatedReading
from app.domain.entities.reading import Reading
from app.domain.value_objects.comfort_status import ComfortStatus


def test_get_reading_history_returns_only_requested_device() -> None:
    repository = FakeReadingRepository()
    target_reading = Reading(
        device_id="esp32-sala-101",
        room_id="sala-101",
        timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        temperature=23.0,
        humidity=50.0,
        luminosity=400.0,
    )
    other_reading = Reading(
        device_id="esp32-sala-202",
        room_id="sala-202",
        timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        temperature=25.0,
        humidity=45.0,
        luminosity=350.0,
    )
    repository.history = [
        EvaluatedReading(reading=target_reading, comfort_status=ComfortStatus.OK),
        EvaluatedReading(reading=other_reading, comfort_status=ComfortStatus.OK),
    ]

    use_case = GetReadingHistory(repository)
    result = use_case.execute(device_id="esp32-sala-101", start="-1h", stop="now()", window="1m")

    assert len(result) == 1
    assert result[0].device_id == "esp32-sala-101"
