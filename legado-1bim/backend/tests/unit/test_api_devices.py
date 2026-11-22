from __future__ import annotations

from datetime import UTC, datetime

from fakes import FakeMessageSubscriber
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.use_cases.list_devices import ListDevices
from app.domain.entities.device_connection import DeviceConnection
from app.presentation.api.v1.dependencies import get_list_devices_use_case


def test_get_devices_returns_serialized_list(api_app: FastAPI) -> None:
    subscriber = FakeMessageSubscriber(
        devices=[
            DeviceConnection(
                device_id="esp32-sala-101",
                room_id="sala-101",
                online=True,
                last_seen=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
            )
        ]
    )
    api_app.dependency_overrides[get_list_devices_use_case] = lambda: ListDevices(subscriber)

    with TestClient(api_app) as client:
        response = client.get("/api/v1/devices")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["device_id"] == "esp32-sala-101"
    assert body[0]["online"] is True


def test_get_devices_returns_empty_list_when_no_devices_known(api_app: FastAPI) -> None:
    subscriber = FakeMessageSubscriber(devices=[])
    api_app.dependency_overrides[get_list_devices_use_case] = lambda: ListDevices(subscriber)

    with TestClient(api_app) as client:
        response = client.get("/api/v1/devices")

    assert response.status_code == 200
    assert response.json() == []
