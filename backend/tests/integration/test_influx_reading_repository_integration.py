"""Teste de integracao: InfluxReadingRepository contra um InfluxDB real.

Requer o InfluxDB rodando localmente com org/bucket/token configurados
(ver infra/influxdb/setup.md) e as variaveis de ambiente INFLUXDB_URL,
INFLUXDB_ORG, INFLUXDB_BUCKET, INFLUXDB_TOKEN (ou um arquivo backend/.env).
Se o servico nao estiver acessivel, o teste e pulado automaticamente.

Como rodar manualmente:
    cd backend
    .venv\\Scripts\\python.exe -m pytest tests/integration/test_influx_reading_repository.py -v
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

import pytest
from conftest import is_port_open
from influxdb_client import InfluxDBClient

from app.domain.entities.evaluated_reading import EvaluatedReading
from app.domain.entities.reading import Reading
from app.domain.services.comfort_evaluator import ComfortEvaluator
from app.domain.value_objects.comfort_status import ComfortStatus
from app.domain.value_objects.comfort_thresholds import ComfortThresholds
from app.infrastructure.influx.influx_reading_repository import InfluxReadingRepository

INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "ecosala-org")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "ecosala")

requires_influxdb = pytest.mark.skipif(
    not INFLUXDB_TOKEN or not is_port_open("localhost", 8086),
    reason=(
        "InfluxDB indisponivel ou INFLUXDB_TOKEN nao configurado "
        "(ver infra/influxdb/setup.md e backend/.env.example)"
    ),
)


def make_repository() -> InfluxReadingRepository:
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
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
    return InfluxReadingRepository(
        client=client,
        bucket=INFLUXDB_BUCKET,
        org=INFLUXDB_ORG,
        comfort_evaluator=ComfortEvaluator(thresholds),
    )


@requires_influxdb
def test_save_and_get_latest_roundtrip() -> None:
    repository = make_repository()
    device_id = f"esp32-teste-integracao-{int(time.time())}"
    reading = Reading(
        device_id=device_id,
        room_id="sala-teste-integracao",
        timestamp=datetime.now(UTC),
        temperature=24.5,
        humidity=50.0,
        luminosity=400.0,
    )

    repository.save(EvaluatedReading(reading=reading, comfort_status=ComfortStatus.OK))
    time.sleep(1)  # da tempo do InfluxDB indexar o ponto recem-gravado

    latest = repository.get_latest(room_id="sala-teste-integracao")

    matching = [item for item in latest if item.reading.device_id == device_id]
    assert len(matching) == 1
    assert matching[0].comfort_status == ComfortStatus.OK
    assert matching[0].reading.temperature == pytest.approx(24.5)


@requires_influxdb
def test_get_history_returns_aggregated_points() -> None:
    repository = make_repository()
    device_id = f"esp32-teste-historico-{int(time.time())}"
    reading = Reading(
        device_id=device_id,
        room_id="sala-teste-integracao",
        timestamp=datetime.now(UTC),
        temperature=30.0,
        humidity=50.0,
        luminosity=400.0,
    )
    repository.save(EvaluatedReading(reading=reading, comfort_status=ComfortStatus.CRITICO))
    time.sleep(1)

    history = repository.get_history(device_id=device_id, start="-5m", stop="now()", window="1m")

    assert len(history) >= 1
    assert history[0].reading.device_id == device_id
    # Status recalculado a partir do valor agregado, nao da tag original
    assert history[0].comfort_status == ComfortStatus.CRITICO
