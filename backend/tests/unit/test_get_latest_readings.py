from __future__ import annotations

from datetime import UTC, datetime

from fakes import FakeReadingRepository

from app.application.use_cases.get_latest_readings import GetLatestReadings
from app.domain.entities.evaluated_reading import EvaluatedReading
from app.domain.entities.reading import Reading
from app.domain.value_objects.comfort_status import ComfortStatus


def test_get_latest_readings_maps_repository_data_to_dto() -> None:
    repository = FakeReadingRepository()
    reading = Reading(
        device_id="esp32-sala-101",
        room_id="sala-101",
        timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        temperature=23.0,
        humidity=50.0,
        luminosity=400.0,
    )
    repository.latest_by_room[None] = [
        EvaluatedReading(reading=reading, comfort_status=ComfortStatus.OK)
    ]

    use_case = GetLatestReadings(repository)
    result = use_case.execute()

    assert len(result) == 1
    assert result[0].device_id == "esp32-sala-101"
    assert result[0].comfort_status == ComfortStatus.OK


def test_get_latest_readings_filters_by_room_id() -> None:
    repository = FakeReadingRepository()
    reading = Reading(
        device_id="esp32-sala-202",
        room_id="sala-202",
        timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        temperature=25.0,
        humidity=45.0,
        luminosity=350.0,
    )
    repository.latest_by_room["sala-202"] = [
        EvaluatedReading(reading=reading, comfort_status=ComfortStatus.OK)
    ]

    use_case = GetLatestReadings(repository)
    result = use_case.execute(room_id="sala-202")

    assert len(result) == 1
    assert result[0].room_id == "sala-202"
