"""Teste de integracao: PahoMessageSubscriber contra um Mosquitto real.

Requer o Mosquitto rodando localmente com os usuarios "device" e "backend"
configurados (ver infra/mosquitto/). Se o broker nao estiver acessivel, o
teste e pulado automaticamente.

Como rodar manualmente:
    cd backend
    .venv\\Scripts\\python.exe -m pytest tests/integration/test_paho_subscriber.py -v
"""

from __future__ import annotations

import json
import os
import time

import paho.mqtt.publish as mqtt_publish
import pytest
from conftest import FakeReadingRepository, is_port_open

from app.application.use_cases.ingest_reading import IngestReading
from app.domain.services.comfort_evaluator import ComfortEvaluator
from app.domain.value_objects.comfort_thresholds import ComfortThresholds
from app.infrastructure.mqtt.paho_subscriber import PahoMessageSubscriber

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_BACKEND_USERNAME = os.environ.get("MQTT_USERNAME", "backend")
MQTT_BACKEND_PASSWORD = os.environ.get("MQTT_PASSWORD", "dev-backend-2026")
MQTT_DEVICE_USERNAME = os.environ.get("MQTT_DEVICE_USERNAME", "device")
MQTT_DEVICE_PASSWORD = os.environ.get("MQTT_DEVICE_PASSWORD", "dev-esp32-2026")

requires_mosquitto = pytest.mark.skipif(
    not is_port_open(MQTT_HOST, MQTT_PORT),
    reason=f"Mosquitto indisponivel em {MQTT_HOST}:{MQTT_PORT} (ver infra/mosquitto/)",
)


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


@requires_mosquitto
def test_subscriber_ingests_published_telemetry() -> None:
    repository = FakeReadingRepository()
    evaluator = ComfortEvaluator(make_thresholds())
    ingest_reading = IngestReading(repository=repository, evaluator=evaluator)
    subscriber = PahoMessageSubscriber(
        host=MQTT_HOST,
        port=MQTT_PORT,
        username=MQTT_BACKEND_USERNAME,
        password=MQTT_BACKEND_PASSWORD,
        ingest_reading=ingest_reading,
        client_id="ecosala-test-subscriber",
    )
    subscriber.start()
    time.sleep(1)  # da tempo da conexao/subscribe se estabelecerem

    device_id = f"esp32-teste-{int(time.time())}"
    payload = {
        "device_id": device_id,
        "room_id": "sala-teste",
        "timestamp": int(time.time()),
        "temperature": 23.0,
        "humidity": 50.0,
        "luminosity": 400.0,
    }

    try:
        mqtt_publish.single(
            f"ecosala/v1/sala-teste/{device_id}/telemetry",
            payload=json.dumps(payload),
            qos=1,
            hostname=MQTT_HOST,
            port=MQTT_PORT,
            auth={"username": MQTT_DEVICE_USERNAME, "password": MQTT_DEVICE_PASSWORD},
        )
        time.sleep(1)  # da tempo da mensagem chegar e ser processada

        assert len(repository.saved) == 1
        assert repository.saved[0].reading.device_id == device_id

        devices = subscriber.get_known_devices()
        assert any(d.device_id == device_id and d.online for d in devices)
    finally:
        subscriber.stop()
