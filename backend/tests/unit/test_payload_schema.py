from __future__ import annotations

import json

from app.infrastructure.mqtt.payload_schema import TelemetryPayload, parse_telemetry_payload

VALID_PAYLOAD = {
    "device_id": "esp32-sala-101",
    "room_id": "sala-101",
    "timestamp": 1760000000,
    "temperature": 27.4,
    "humidity": 58.1,
    "luminosity": 412,
}


def encode(data: dict) -> bytes:
    return json.dumps(data).encode("utf-8")


def test_parses_valid_payload() -> None:
    result = parse_telemetry_payload(encode(VALID_PAYLOAD))

    assert result is not None
    assert result.device_id == "esp32-sala-101"
    assert result.room_id == "sala-101"
    assert result.temperature == 27.4


def test_rejects_malformed_json() -> None:
    assert parse_telemetry_payload(b"not-json-at-all") is None


def test_rejects_missing_required_field() -> None:
    data = dict(VALID_PAYLOAD)
    del data["temperature"]

    assert parse_telemetry_payload(encode(data)) is None


def test_rejects_temperature_out_of_plausible_range() -> None:
    data = {**VALID_PAYLOAD, "temperature": 500.0}

    assert parse_telemetry_payload(encode(data)) is None


def test_rejects_humidity_out_of_plausible_range() -> None:
    data = {**VALID_PAYLOAD, "humidity": -5.0}

    assert parse_telemetry_payload(encode(data)) is None


def test_rejects_negative_timestamp() -> None:
    data = {**VALID_PAYLOAD, "timestamp": -1}

    assert parse_telemetry_payload(encode(data)) is None


def test_rejects_empty_device_id() -> None:
    data = {**VALID_PAYLOAD, "device_id": ""}

    assert parse_telemetry_payload(encode(data)) is None


def test_to_datetime_converts_unix_timestamp() -> None:
    payload = TelemetryPayload.model_validate(VALID_PAYLOAD)

    assert payload.to_datetime().timestamp() == VALID_PAYLOAD["timestamp"]
