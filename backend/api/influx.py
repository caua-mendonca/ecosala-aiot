"""Consultas ao InfluxDB (histórico das leituras e previsões)."""
from __future__ import annotations

import re
from typing import Any

from influxdb_client import InfluxDBClient

from ecosala_common.config import INFLUX_BUCKET, INFLUX_ORG, INFLUX_URL, env

RANGES = {"15m": "1m", "1h": "1m", "6h": "5m", "24h": "15m", "7d": "1h"}
FIELDS = {"value", "state", "vibration", "current", "temperature", "ambient_temp", "load", "running",
          "health", "rul_h", "trend"}
MEASUREMENTS = {"sensor", "actuator", "equipment", "prediction"}
_ID = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
_client: InfluxDBClient | None = None


def client() -> InfluxDBClient:
    global _client
    if _client is None:
        _client = InfluxDBClient(url=INFLUX_URL, token=env("INFLUXDB_TOKEN"), org=INFLUX_ORG, timeout=15000)
    return _client


def history(device: str, measurement: str, field: str, rng: str) -> list[dict[str, Any]]:
    if not _ID.match(device) or measurement not in MEASUREMENTS or field not in FIELDS or rng not in RANGES:
        raise ValueError("parâmetros inválidos")
    flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{rng})
  |> filter(fn: (r) => r._measurement == "{measurement}" and r.device == "{device}" and r._field == "{field}")
  |> aggregateWindow(every: {RANGES[rng]}, fn: mean, createEmpty: false)
'''
    rows = []
    for table in client().query_api().query(flux, org=INFLUX_ORG):
        for rec in table.records:
            rows.append({"ts": rec.get_time().isoformat(), "value": rec.get_value()})
    return rows


def stats(device: str, measurement: str, field: str, rng: str) -> dict[str, Any]:
    pts = [p["value"] for p in history(device, measurement, field, rng) if p["value"] is not None]
    if not pts:
        return {"count": 0}
    return {"count": len(pts), "min": min(pts), "max": max(pts), "mean": sum(pts) / len(pts)}


def latest(minutes: int = 30) -> dict[str, dict[str, Any]]:
    flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{int(minutes)}m)
  |> filter(fn: (r) => r._measurement == "sensor" or r._measurement == "equipment" or r._measurement == "actuator")
  |> last()
'''
    out: dict[str, dict[str, Any]] = {}
    for table in client().query_api().query(flux, org=INFLUX_ORG):
        for rec in table.records:
            d = out.setdefault(rec.values.get("device"), {"measurement": rec.get_measurement(),
                                                          "room": rec.values.get("room")})
            d[rec.get_field()] = rec.get_value()
            d["ts"] = rec.get_time().isoformat()
    return out


def ping() -> bool:
    try:
        return bool(client().ping())
    except Exception:  # noqa: BLE001
        return False
