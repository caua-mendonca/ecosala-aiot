from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.domain.value_objects.comfort_status import ComfortStatus


class ReadingSummarySchema(BaseModel):
    device_id: str
    room_id: str
    timestamp: datetime
    temperature: float
    humidity: float
    luminosity: float
    comfort_status: ComfortStatus


class DeviceSchema(BaseModel):
    device_id: str
    room_id: str
    online: bool
    last_seen: datetime | None


class ComfortThresholdsSchema(BaseModel):
    temperature_min_c: float
    temperature_max_c: float
    humidity_min_percent: float
    humidity_max_percent: float
    luminosity_min_lux: float
    temperature_critical_margin_c: float
    humidity_critical_margin_percent: float
    luminosity_critical_margin_lux: float


class HealthSchema(BaseModel):
    status: str
    mqtt_connected: bool
    influxdb_connected: bool
