from __future__ import annotations

import logging

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.flux_table import FluxTable
from influxdb_client.client.write_api import SYNCHRONOUS

from app.domain.entities.evaluated_reading import EvaluatedReading
from app.domain.entities.reading import Reading
from app.domain.services.comfort_evaluator import ComfortEvaluator
from app.domain.value_objects.comfort_status import ComfortStatus

logger = logging.getLogger(__name__)

MEASUREMENT_NAME = "environment"
DEFAULT_LATEST_LOOKBACK = "-30d"


class InfluxReadingRepository:
    def __init__(
        self,
        client: InfluxDBClient,
        bucket: str,
        org: str,
        comfort_evaluator: ComfortEvaluator,
    ) -> None:
        self._bucket = bucket
        self._org = org
        self._comfort_evaluator = comfort_evaluator
        self._write_api = client.write_api(write_options=SYNCHRONOUS)
        self._query_api = client.query_api()

    def save(self, evaluated_reading: EvaluatedReading) -> None:
        reading = evaluated_reading.reading
        point = (
            Point(MEASUREMENT_NAME)
            .tag("device_id", reading.device_id)
            .tag("room_id", reading.room_id)
            .tag("comfort_status", evaluated_reading.comfort_status.value)
            .field("temperature", reading.temperature)
            .field("humidity", reading.humidity)
            .field("luminosity", reading.luminosity)
            .time(reading.timestamp, WritePrecision.S)
        )
        try:
            self._write_api.write(bucket=self._bucket, org=self._org, record=point)
        except Exception:
            logger.exception(
                "Falha ao gravar leitura no InfluxDB (device_id=%s)", reading.device_id
            )

    def get_latest(self, room_id: str | None = None) -> list[EvaluatedReading]:
        room_filter = f'|> filter(fn: (r) => r.room_id == "{room_id}")\n  ' if room_id else ""
        query = f"""
        from(bucket: "{self._bucket}")
          |> range(start: {DEFAULT_LATEST_LOOKBACK})
          |> filter(fn: (r) => r._measurement == "{MEASUREMENT_NAME}")
          {room_filter}|> group(columns: ["device_id", "room_id", "_field"])
          |> last()
          |> pivot(
              rowKey: ["_time", "device_id", "room_id", "comfort_status"],
              columnKey: ["_field"],
              valueColumn: "_value"
          )
        """
        results: list[EvaluatedReading] = []
        for table in self._query(query):
            for record in table.records:
                reading = Reading(
                    device_id=str(record.values["device_id"]),
                    room_id=str(record.values["room_id"]),
                    timestamp=record.get_time(),
                    temperature=float(record.values["temperature"]),
                    humidity=float(record.values["humidity"]),
                    luminosity=float(record.values["luminosity"]),
                )
                comfort_status = ComfortStatus(str(record.values["comfort_status"]))
                results.append(EvaluatedReading(reading=reading, comfort_status=comfort_status))
        return results

    def get_history(
        self, device_id: str, start: str, stop: str, window: str
    ) -> list[EvaluatedReading]:
        query = f"""
        from(bucket: "{self._bucket}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r._measurement == "{MEASUREMENT_NAME}")
          |> filter(fn: (r) => r.device_id == "{device_id}")
          |> drop(columns: ["comfort_status"])
          |> aggregateWindow(every: {window}, fn: mean, createEmpty: false)
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        """
        results: list[EvaluatedReading] = []
        for table in self._query(query):
            for record in table.records:
                reading = Reading(
                    device_id=device_id,
                    room_id=str(record.values.get("room_id", "")),
                    timestamp=record.get_time(),
                    temperature=float(record.values["temperature"]),
                    humidity=float(record.values["humidity"]),
                    luminosity=float(record.values["luminosity"]),
                )
                comfort_status = self._comfort_evaluator.evaluate(reading)
                results.append(EvaluatedReading(reading=reading, comfort_status=comfort_status))
        return results

    def _query(self, flux_query: str) -> list[FluxTable]:
        try:
            return self._query_api.query(flux_query, org=self._org)
        except Exception:
            logger.exception("Falha ao consultar o InfluxDB")
            return []
