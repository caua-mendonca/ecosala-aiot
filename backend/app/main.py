from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from influxdb_client import InfluxDBClient

from app.application.use_cases.get_latest_readings import GetLatestReadings
from app.application.use_cases.get_reading_history import GetReadingHistory
from app.application.use_cases.ingest_reading import IngestReading
from app.application.use_cases.list_devices import ListDevices
from app.core.config import Settings
from app.core.logging import configure_logging
from app.domain.services.comfort_evaluator import ComfortEvaluator
from app.infrastructure.influx.influx_reading_repository import InfluxReadingRepository
from app.infrastructure.mqtt.paho_subscriber import PahoMessageSubscriber
from app.presentation.api.v1.routes import devices, health, readings

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"


def _build_lifespan(settings: Settings):  # type: ignore[no-untyped-def]
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        thresholds = settings.to_comfort_thresholds()
        comfort_evaluator = ComfortEvaluator(thresholds)

        influx_client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        reading_repository = InfluxReadingRepository(
            client=influx_client,
            bucket=settings.influxdb_bucket,
            org=settings.influxdb_org,
            comfort_evaluator=comfort_evaluator,
        )

        ingest_reading = IngestReading(repository=reading_repository, evaluator=comfort_evaluator)
        message_subscriber = PahoMessageSubscriber(
            host=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username,
            password=settings.mqtt_password,
            ingest_reading=ingest_reading,
        )
        message_subscriber.start()
        logger.info("Backend EcoSala iniciado (MQTT %s:%s)", settings.mqtt_host, settings.mqtt_port)

        app.state.settings = settings
        app.state.thresholds = thresholds
        app.state.influx_client = influx_client
        app.state.message_subscriber = message_subscriber
        app.state.get_latest_readings = GetLatestReadings(reading_repository)
        app.state.get_reading_history = GetReadingHistory(reading_repository)
        app.state.list_devices = ListDevices(message_subscriber)

        try:
            yield
        finally:
            message_subscriber.stop()
            influx_client.close()  # type: ignore[no-untyped-call]
            logger.info("Backend EcoSala encerrado")

    return lifespan


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="EcoSala API",
        description="API do EcoSala - monitoramento de conforto ambiental em salas de aula",
        version="0.1.0",
        lifespan=_build_lifespan(settings),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_allowed_origin],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Erro inesperado ao processar %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Erro interno no servidor."})

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(devices.router, prefix=API_PREFIX)
    app.include_router(readings.router, prefix=API_PREFIX)

    return app


app = create_app()
