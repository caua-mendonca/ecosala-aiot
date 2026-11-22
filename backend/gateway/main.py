"""Gateway MQTT <-> RabbitMQ.

IoT -> Web : lê a telemetria do Mosquitto, quebra a mensagem de cada nó em uma
             mensagem por dispositivo (formato único) e publica no exchange
             topic ecosala.telemetry com routing key telemetry.<zona>.<tipo>.<id>.
Web -> IoT : consome a fila q.commands e publica o comando no tópico MQTT
             ecosala/v1/<zona>/<nó>/command.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import time

import paho.mqtt.client as mqtt

from ecosala_common import topology as T
from ecosala_common.config import env, env_int
from ecosala_common.envelope import InvalidEnvelope, decode, make_envelope
from ecosala_common.health import beat
from ecosala_common.rabbit import connect, publish

log = logging.getLogger("gateway")
PREFIX = "ecosala/v1"


def split_telemetry(topic: str, raw: bytes) -> list[tuple[str, dict]]:
    """Converte uma mensagem MQTT em [(routing_key, envelope)]."""
    parts = topic.split("/")
    if len(parts) != 5 or parts[0] != "ecosala" or parts[1] != "v1":
        raise ValueError(f"tópico fora do contrato: {topic}")
    room, node, kind = parts[2], parts[3], parts[4]
    out: list[tuple[str, dict]] = []
    if kind == "status":
        state = raw.decode("utf-8", "replace").strip()
        env_ = make_envelope("status", node, {"state": state}, room=room)
        return [(T.key("status", room, node), env_)]
    data = json.loads(raw)
    if kind == "ack":
        env_ = make_envelope("command.ack", data.get("target"), data, room=room)
        return [(T.key("ack", room, str(data.get("target"))), env_)]
    if kind != "telemetry":
        raise ValueError(f"tipo de tópico desconhecido: {kind}")
    ts = data.get("ts")
    sim_time = data.get("sim_time")
    for dev_id, s in (data.get("sensors") or {}).items():
        value = s.get("value")
        if not isinstance(value, (int, float)):
            continue
        env_ = make_envelope("telemetry", dev_id, {"kind": "sensor", "sensor_type": s.get("type"),
                                                    "value": float(value), "sim_time": sim_time},
                             room=room, ts=ts)
        out.append((T.telemetry_key(room, str(s.get("type")), dev_id), env_))
    for dev_id, a in (data.get("actuators") or {}).items():
        env_ = make_envelope("telemetry", dev_id, {"kind": "actuator", "actuator_type": a.get("type"),
                                                    "state": bool(a.get("state")), "sim_time": sim_time},
                             room=room, ts=ts)
        out.append((T.telemetry_key(room, "actuator", dev_id), env_))
    for dev_id, e in (data.get("equipment") or {}).items():
        payload = {k: e.get(k) for k in ("vibration", "current", "temperature", "ambient_temp", "load",
                                         "running", "enabled", "failed")}
        payload.update({"kind": "equipment", "equipment_type": e.get("type"), "sim_time": sim_time})
        env_ = make_envelope("telemetry", dev_id, payload, room=room, ts=ts)
        out.append((T.telemetry_key(room, "equipment", dev_id), env_))
    return out


def command_to_mqtt(msg: dict) -> tuple[str, dict]:
    p = msg["payload"]
    room = msg.get("room") or p.get("room")
    node = p.get("node")
    if not room or not node:
        raise InvalidEnvelope("comando sem sala/nó")
    body = {"id": msg["id"], "target": msg.get("device"), "action": p.get("action"),
            "params": p.get("params") or {}, "issued_by": p.get("issued_by"), "ts": msg["ts"]}
    return f"{PREFIX}/{room}/{node}/command", body


class Gateway:
    def __init__(self) -> None:
        self.inbox: queue.Queue[tuple[str, bytes]] = queue.Queue(maxsize=50000)
        self.mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"gateway-{os.getpid()}")
        self.mqtt.username_pw_set(env("MQTT_GATEWAY_USER", "gateway"), env("MQTT_GATEWAY_PASSWORD"))
        self.mqtt.on_connect = self._on_connect
        self.mqtt.on_message = lambda c, u, m: self.inbox.put((m.topic, m.payload))
        self.mqtt.reconnect_delay_set(1, 10)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):  # noqa: ANN001
        log.info("conectado ao Mosquitto (%s)", reason_code)
        for suffix in ("telemetry", "status", "ack"):
            client.subscribe(f"{PREFIX}/+/+/{suffix}", qos=1)

    def run(self) -> None:
        while True:
            try:
                self.mqtt.connect(os.getenv("MQTT_HOST", "mosquitto"), env_int("MQTT_PORT", 1883), keepalive=30)
                break
            except OSError as exc:
                log.warning("Mosquitto indisponível (%s)", exc)
                time.sleep(2)
        self.mqtt.loop_start()
        while True:
            conn = connect()
            ch = conn.channel()
            ch.basic_qos(prefetch_count=20)

            def on_command(chan, method, props, body):  # noqa: ANN001
                try:
                    msg = decode(body)
                    topic, payload = command_to_mqtt(msg)
                    info = self.mqtt.publish(topic, json.dumps(payload), qos=1)
                    info.wait_for_publish(timeout=5)
                    chan.basic_ack(method.delivery_tag)
                    log.info("comando %s -> %s", payload["action"], topic)
                except Exception as exc:  # noqa: BLE001
                    log.warning("comando com erro -> DLQ: %s", exc)
                    chan.basic_nack(method.delivery_tag, requeue=False)

            ch.basic_consume(T.Q_COMMANDS, on_command)
            try:
                while True:
                    conn.process_data_events(time_limit=0.05)
                    beat()
                    for _ in range(2000):
                        try:
                            topic, raw = self.inbox.get_nowait()
                        except queue.Empty:
                            break
                        try:
                            for rk, envelope in split_telemetry(topic, raw):
                                publish(ch, T.EX_TELEMETRY, rk, envelope)
                        except (ValueError, json.JSONDecodeError) as exc:
                            log.warning("mensagem MQTT descartada (%s): %s", topic, exc)
            except Exception as exc:  # noqa: BLE001
                log.warning("RabbitMQ caiu (%s); reconectando", exc)
                time.sleep(2)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    Gateway().run()


if __name__ == "__main__":
    main()
