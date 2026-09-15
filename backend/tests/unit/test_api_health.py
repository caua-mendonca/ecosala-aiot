from __future__ import annotations

from fakes import FakeMessageSubscriber
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.api.v1.dependencies import get_influx_client, get_message_subscriber


class FakeInfluxClient:
    def __init__(self, ping_result: bool = True, raise_error: bool = False) -> None:
        self._ping_result = ping_result
        self._raise_error = raise_error

    def ping(self) -> bool:
        if self._raise_error:
            raise ConnectionError("influxdb indisponivel")
        return self._ping_result


def test_health_reports_ok_when_both_services_connected(api_app: FastAPI) -> None:
    api_app.dependency_overrides[get_message_subscriber] = lambda: FakeMessageSubscriber(
        connected=True
    )
    api_app.dependency_overrides[get_influx_client] = lambda: FakeInfluxClient(ping_result=True)

    with TestClient(api_app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mqtt_connected": True,
        "influxdb_connected": True,
    }


def test_health_reports_degraded_when_mqtt_down(api_app: FastAPI) -> None:
    api_app.dependency_overrides[get_message_subscriber] = lambda: FakeMessageSubscriber(
        connected=False
    )
    api_app.dependency_overrides[get_influx_client] = lambda: FakeInfluxClient(ping_result=True)

    with TestClient(api_app) as client:
        response = client.get("/api/v1/health")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["mqtt_connected"] is False


def test_health_handles_influxdb_ping_exception_gracefully(api_app: FastAPI) -> None:
    api_app.dependency_overrides[get_message_subscriber] = lambda: FakeMessageSubscriber(
        connected=True
    )
    api_app.dependency_overrides[get_influx_client] = lambda: FakeInfluxClient(raise_error=True)

    with TestClient(api_app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["influxdb_connected"] is False
    assert body["status"] == "degraded"
