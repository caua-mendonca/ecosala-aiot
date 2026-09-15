from __future__ import annotations

from datetime import UTC, datetime

from fakes import FakeReadingRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.use_cases.get_latest_readings import GetLatestReadings
from app.application.use_cases.get_reading_history import GetReadingHistory
from app.domain.entities.evaluated_reading import EvaluatedReading
from app.domain.entities.reading import Reading
from app.domain.value_objects.comfort_status import ComfortStatus
from app.domain.value_objects.comfort_thresholds import ComfortThresholds
from app.presentation.api.v1.dependencies import (
    get_comfort_thresholds,
    get_latest_readings_use_case,
    get_reading_history_use_case,
)


def test_get_latest_readings_returns_serialized_list(api_app: FastAPI) -> None:
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
    api_app.dependency_overrides[get_latest_readings_use_case] = lambda: GetLatestReadings(
        repository
    )

    with TestClient(api_app) as client:
        response = client.get("/api/v1/readings/latest")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["device_id"] == "esp32-sala-101"
    assert body[0]["comfort_status"] == "OK"


def test_get_latest_readings_passes_room_id_filter(api_app: FastAPI) -> None:
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
    api_app.dependency_overrides[get_latest_readings_use_case] = lambda: GetLatestReadings(
        repository
    )

    with TestClient(api_app) as client:
        response = client.get("/api/v1/readings/latest", params={"room_id": "sala-202"})

    assert response.status_code == 200
    assert response.json()[0]["room_id"] == "sala-202"


def test_get_reading_history_requires_device_id(api_app: FastAPI) -> None:
    # FastAPI resolve as dependencies antes de finalizar a validacao dos
    # query params; sem um override, a dependency real tentaria acessar
    # app.state (inexistente nesta app de teste sem lifespan).
    api_app.dependency_overrides[get_reading_history_use_case] = lambda: GetReadingHistory(
        FakeReadingRepository()
    )

    with TestClient(api_app) as client:
        response = client.get("/api/v1/readings/history")

    assert response.status_code == 422


def test_get_reading_history_returns_serialized_list(api_app: FastAPI) -> None:
    repository = FakeReadingRepository()
    reading = Reading(
        device_id="esp32-sala-101",
        room_id="sala-101",
        timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        temperature=23.0,
        humidity=50.0,
        luminosity=400.0,
    )
    repository.history = [EvaluatedReading(reading=reading, comfort_status=ComfortStatus.OK)]
    api_app.dependency_overrides[get_reading_history_use_case] = lambda: GetReadingHistory(
        repository
    )

    with TestClient(api_app) as client:
        response = client.get(
            "/api/v1/readings/history",
            params={"device_id": "esp32-sala-101", "start": "-1h", "stop": "now()", "window": "1m"},
        )

    assert response.status_code == 200
    assert response.json()[0]["device_id"] == "esp32-sala-101"


def test_get_comfort_thresholds_returns_configured_values(api_app: FastAPI) -> None:
    thresholds = ComfortThresholds(
        temperature_min_c=20.0,
        temperature_max_c=26.0,
        humidity_min_percent=40.0,
        humidity_max_percent=60.0,
        luminosity_min_lux=300.0,
        temperature_critical_margin_c=4.0,
        humidity_critical_margin_percent=15.0,
        luminosity_critical_margin_lux=150.0,
    )
    api_app.dependency_overrides[get_comfort_thresholds] = lambda: thresholds

    with TestClient(api_app) as client:
        response = client.get("/api/v1/comfort/thresholds")

    assert response.status_code == 200
    assert response.json()["temperature_min_c"] == 20.0
    assert response.json()["luminosity_min_lux"] == 300.0
