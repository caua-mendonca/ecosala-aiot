from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.value_objects.comfort_thresholds import ComfortThresholds


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = "backend"
    mqtt_password: str = ""

    influxdb_url: str = "http://localhost:8086"
    influxdb_org: str = "ecosala-org"
    influxdb_bucket: str = "ecosala"
    influxdb_token: str = ""

    comfort_temperature_min_c: float = 20.0
    comfort_temperature_max_c: float = 26.0
    comfort_humidity_min_percent: float = 40.0
    comfort_humidity_max_percent: float = 60.0
    comfort_luminosity_min_lux: float = 300.0
    comfort_temperature_critical_margin_c: float = 4.0
    comfort_humidity_critical_margin_percent: float = 15.0
    comfort_luminosity_critical_margin_lux: float = 150.0

    cors_allowed_origin: str = "http://localhost:5173"
    log_level: str = "INFO"

    def to_comfort_thresholds(self) -> ComfortThresholds:
        return ComfortThresholds(
            temperature_min_c=self.comfort_temperature_min_c,
            temperature_max_c=self.comfort_temperature_max_c,
            humidity_min_percent=self.comfort_humidity_min_percent,
            humidity_max_percent=self.comfort_humidity_max_percent,
            luminosity_min_lux=self.comfort_luminosity_min_lux,
            temperature_critical_margin_c=self.comfort_temperature_critical_margin_c,
            humidity_critical_margin_percent=self.comfort_humidity_critical_margin_percent,
            luminosity_critical_margin_lux=self.comfort_luminosity_critical_margin_lux,
        )
