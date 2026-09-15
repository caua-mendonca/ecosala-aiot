"""GET /health - status da API, da conexao MQTT e do InfluxDB."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from influxdb_client import InfluxDBClient

from app.domain.ports.message_subscriber import MessageSubscriber
from app.presentation.api.v1.dependencies import get_influx_client, get_message_subscriber
from app.presentation.api.v1.schemas import HealthSchema

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthSchema)
def get_health(
    message_subscriber: MessageSubscriber = Depends(get_message_subscriber),
    influx_client: InfluxDBClient = Depends(get_influx_client),
) -> HealthSchema:
    mqtt_connected = message_subscriber.is_connected()

    try:
        influxdb_connected = bool(influx_client.ping())
    except Exception:
        logger.warning("Falha ao verificar conectividade com o InfluxDB", exc_info=True)
        influxdb_connected = False

    overall_status = "ok" if mqtt_connected and influxdb_connected else "degraded"

    return HealthSchema(
        status=overall_status,
        mqtt_connected=mqtt_connected,
        influxdb_connected=influxdb_connected,
    )
