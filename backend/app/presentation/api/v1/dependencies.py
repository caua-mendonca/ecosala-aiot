"""Provedores de dependencia da API (FastAPI Depends).

Os objetos reais sao construidos uma unica vez na composicao (main.py,
lifespan) e guardados em app.state; estas funcoes apenas os expoem as
rotas. Em testes, cada funcao pode ser substituida via
`app.dependency_overrides` sem precisar subir MQTT/InfluxDB reais.
"""

from __future__ import annotations

from fastapi import Request
from influxdb_client import InfluxDBClient

from app.application.use_cases.get_latest_readings import GetLatestReadings
from app.application.use_cases.get_reading_history import GetReadingHistory
from app.application.use_cases.list_devices import ListDevices
from app.domain.ports.message_subscriber import MessageSubscriber
from app.domain.value_objects.comfort_thresholds import ComfortThresholds


def get_latest_readings_use_case(request: Request) -> GetLatestReadings:
    return request.app.state.get_latest_readings  # type: ignore[no-any-return]


def get_reading_history_use_case(request: Request) -> GetReadingHistory:
    return request.app.state.get_reading_history  # type: ignore[no-any-return]


def get_list_devices_use_case(request: Request) -> ListDevices:
    return request.app.state.list_devices  # type: ignore[no-any-return]


def get_comfort_thresholds(request: Request) -> ComfortThresholds:
    return request.app.state.thresholds  # type: ignore[no-any-return]


def get_message_subscriber(request: Request) -> MessageSubscriber:
    return request.app.state.message_subscriber  # type: ignore[no-any-return]


def get_influx_client(request: Request) -> InfluxDBClient:
    return request.app.state.influx_client  # type: ignore[no-any-return]
