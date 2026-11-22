"""Gravador no InfluxDB: consome q.influx e grava leituras e previsões em lote.

O ack só é enviado ao RabbitMQ depois que o lote foi gravado: se este serviço
parar, as mensagens ficam acumuladas na fila e são gravadas quando ele voltar.
"""
from __future__ import annotations

import logging
import os
import time

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from ecosala_common import topology as T
from ecosala_common.config import INFLUX_BUCKET, INFLUX_ORG, INFLUX_URL, env
from ecosala_common.envelope import InvalidEnvelope, decode
from ecosala_common.health import beat
from ecosala_common.rabbit import connect

log = logging.getLogger("gravador-influx")
BATCH = 500
FLUSH_SECONDS = 0.5


def to_point(msg: dict) -> Point | None:
    p = msg["payload"]
    dev, room, ts = msg.get("device"), msg.get("room") or "?", msg["ts"]
    if msg["type"] == "telemetry":
        kind = p.get("kind")
        if kind == "sensor":
            return (Point("sensor").tag("device", dev).tag("room", room).tag("sensor_type", p.get("sensor_type"))
                    .field("value", float(p["value"])).time(ts, WritePrecision.MS))
        if kind == "actuator":
            return (Point("actuator").tag("device", dev).tag("room", room)
                    .field("state", int(bool(p.get("state")))).time(ts, WritePrecision.MS))
        if kind == "equipment":
            pt = Point("equipment").tag("device", dev).tag("room", room)
            for f in ("vibration", "current", "temperature", "ambient_temp", "load"):
                if isinstance(p.get(f), (int, float)):
                    pt = pt.field(f, float(p[f]))
            pt = pt.field("running", int(bool(p.get("running")))).field("failed", int(bool(p.get("failed"))))
            return pt.time(ts, WritePrecision.MS)
        return None
    if msg["type"] == "prediction":
        pt = Point("prediction").tag("device", dev).tag("room", room)
        for f in ("health", "rul_h", "trend"):
            if isinstance(p.get(f), (int, float)):
                pt = pt.field(f, float(p[f]))
        pt = pt.field("model_version", int(p.get("model_version") or 0))
        return pt.time(ts, WritePrecision.MS)
    return None


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    influx = InfluxDBClient(url=INFLUX_URL, token=env("INFLUXDB_TOKEN"), org=INFLUX_ORG, timeout=20000)
    write_api = influx.write_api(write_options=SYNCHRONOUS)
    while True:
        conn = connect()
        ch = conn.channel()
        ch.basic_qos(prefetch_count=BATCH * 2)
        pending: list[tuple[int, Point | None]] = []
        last_flush = time.time()

        def on_msg(chan, method, props, body):  # noqa: ANN001
            try:
                pending.append((method.delivery_tag, to_point(decode(body))))
            except (InvalidEnvelope, KeyError, TypeError, ValueError) as exc:
                log.warning("mensagem inválida -> DLQ: %s", exc)
                chan.basic_nack(method.delivery_tag, requeue=False)

        ch.basic_consume(T.Q_INFLUX, on_msg)
        log.info("consumindo %s -> InfluxDB bucket %s", T.Q_INFLUX, INFLUX_BUCKET)
        try:
            while True:
                conn.process_data_events(time_limit=0.1)
                beat()
                if pending and (len(pending) >= BATCH or time.time() - last_flush > FLUSH_SECONDS):
                    points = [pt for _, pt in pending if pt is not None]
                    try:
                        if points:
                            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
                        ch.basic_ack(pending[-1][0], multiple=True)
                    except Exception as exc:  # noqa: BLE001
                        log.warning("falha ao gravar no InfluxDB (%s); devolvendo à fila", exc)
                        ch.basic_nack(pending[-1][0], multiple=True, requeue=True)
                        time.sleep(2)
                    pending.clear()
                    last_flush = time.time()
        except Exception as exc:  # noqa: BLE001
            log.warning("conexão perdida (%s); reconectando", exc)
            time.sleep(2)


if __name__ == "__main__":
    main()
