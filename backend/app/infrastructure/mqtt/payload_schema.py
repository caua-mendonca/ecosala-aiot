from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

TEMPERATURE_MIN_C = -40.0
TEMPERATURE_MAX_C = 80.0
HUMIDITY_MIN_PERCENT = 0.0
HUMIDITY_MAX_PERCENT = 100.0
LUMINOSITY_MIN_LUX = 0.0
LUMINOSITY_MAX_LUX = 100_000.0
MIN_PLAUSIBLE_UNIX_TIMESTAMP = 1_577_836_800


class TelemetryPayload(BaseModel):
    device_id: str = Field(min_length=1)
    room_id: str = Field(min_length=1)
    timestamp: int = Field(gt=0)
    temperature: float = Field(ge=TEMPERATURE_MIN_C, le=TEMPERATURE_MAX_C)
    humidity: float = Field(ge=HUMIDITY_MIN_PERCENT, le=HUMIDITY_MAX_PERCENT)
    luminosity: float = Field(ge=LUMINOSITY_MIN_LUX, le=LUMINOSITY_MAX_LUX)

    def to_datetime(self) -> datetime:
        if self.timestamp < MIN_PLAUSIBLE_UNIX_TIMESTAMP:
            return datetime.now(UTC)
        return datetime.fromtimestamp(self.timestamp, tz=UTC)


def parse_telemetry_payload(raw_payload: bytes) -> TelemetryPayload | None:
    try:
        data = json.loads(raw_payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Payload MQTT invalido (JSON malformado): %r", raw_payload)
        return None

    try:
        return TelemetryPayload.model_validate(data)
    except ValidationError as exc:
        logger.warning("Payload MQTT invalido (schema): %s", exc)
        return None
