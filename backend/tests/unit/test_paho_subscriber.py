from __future__ import annotations

import json
from dataclasses import dataclass

from fakes import FakeReadingRepository

from app.application.use_cases.ingest_reading import IngestReading
from app.domain.services.comfort_evaluator import ComfortEvaluator
from app.domain.value_objects.comfort_thresholds import ComfortThresholds
from app.infrastructure.mqtt.paho_subscriber import PahoMessageSubscriber

VALID_PAYLOAD = {
    "device_id": "esp32-sala-101",
    "room_id": "sala-101",
    "timestamp": 1760000000,
    "temperature": 23.0,
    "humidity": 50.0,
    "luminosity": 400.0,
}


@dataclass
class FakeMqttMessage:
    topic: str
    payload: bytes


def make_subscriber() -> tuple[PahoMessageSubscriber, FakeReadingRepository]:
    repository = FakeReadingRepository()
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
    ingest_reading = IngestReading(repository=repository, evaluator=ComfortEvaluator(thresholds))
    subscriber = PahoMessageSubscriber(
        host="localhost",
        port=1883,
        username="backend",
        password="changeme",
        ingest_reading=ingest_reading,
    )
    return subscriber, repository


def test_handle_telemetry_ingests_valid_payload_and_marks_device_online() -> None:
    subscriber, repository = make_subscriber()

    subscriber._handle_telemetry(
        "esp32-sala-101", "sala-101", json.dumps(VALID_PAYLOAD).encode("utf-8")
    )

    assert len(repository.saved) == 1
    devices = subscriber.get_known_devices()
    assert len(devices) == 1
    assert devices[0].device_id == "esp32-sala-101"
    assert devices[0].online is True


def test_handle_telemetry_ignores_invalid_payload_and_does_not_touch_device() -> None:
    subscriber, repository = make_subscriber()

    subscriber._handle_telemetry("esp32-sala-101", "sala-101", b"not-json")

    assert repository.saved == []
    assert subscriber.get_known_devices() == []


def test_handle_status_updates_online_and_offline() -> None:
    subscriber, _ = make_subscriber()

    subscriber._handle_status("esp32-sala-101", "sala-101", b"online")
    assert subscriber.get_known_devices()[0].online is True

    subscriber._handle_status("esp32-sala-101", "sala-101", b"offline")
    assert subscriber.get_known_devices()[0].online is False


def test_on_message_routes_telemetry_topic() -> None:
    subscriber, repository = make_subscriber()
    message = FakeMqttMessage(
        topic="ecosala/v1/sala-101/esp32-sala-101/telemetry",
        payload=json.dumps(VALID_PAYLOAD).encode("utf-8"),
    )

    subscriber._on_message(None, None, message)

    assert len(repository.saved) == 1


def test_on_message_routes_status_topic() -> None:
    subscriber, _ = make_subscriber()
    message = FakeMqttMessage(
        topic="ecosala/v1/sala-101/esp32-sala-101/status", payload=b"online"
    )

    subscriber._on_message(None, None, message)

    assert subscriber.get_known_devices()[0].online is True


def test_on_message_ignores_topic_outside_contract() -> None:
    subscriber, repository = make_subscriber()
    message = FakeMqttMessage(topic="outro/topico/qualquer", payload=b"x")

    subscriber._on_message(None, None, message)

    assert repository.saved == []
    assert subscriber.get_known_devices() == []
