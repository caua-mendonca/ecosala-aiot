from __future__ import annotations

import argparse
import json
import random
import signal
import sys
import time
from dataclasses import dataclass

import paho.mqtt.client as mqtt

TOPIC_PREFIX = "ecosala/v1"

TEMPERATURE_BASE_C = 24.0
TEMPERATURE_VARIATION_C = 4.0
HUMIDITY_BASE_PERCENT = 50.0
HUMIDITY_VARIATION_PERCENT = 12.0
LUMINOSITY_BASE_LUX = 400.0
LUMINOSITY_VARIATION_LUX = 200.0


@dataclass(frozen=True)
class SimulatorConfig:
    host: str
    port: int
    username: str
    password: str
    room_id: str
    device_id: str
    interval_seconds: float


def parse_args() -> SimulatorConfig:
    parser = argparse.ArgumentParser(description="Simulador de dispositivo EcoSala")
    parser.add_argument("--host", default="localhost", help="Host do broker MQTT")
    parser.add_argument("--port", type=int, default=1883, help="Porta do broker MQTT")
    parser.add_argument("--username", default="device", help="Usuario MQTT")
    parser.add_argument("--password", default="dev-esp32-2026", help="Senha MQTT")
    parser.add_argument("--room-id", default="sala-101", help="Identificador da sala")
    parser.add_argument(
        "--device-id", default="esp32-sala-101", help="Identificador do dispositivo"
    )
    parser.add_argument(
        "--interval", type=float, default=5.0, help="Intervalo entre publicacoes (segundos)"
    )
    args = parser.parse_args()

    return SimulatorConfig(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        room_id=args.room_id,
        device_id=args.device_id,
        interval_seconds=args.interval,
    )


def build_reading(config: SimulatorConfig) -> dict:
    return {
        "device_id": config.device_id,
        "room_id": config.room_id,
        "timestamp": int(time.time()),
        "temperature": round(
            TEMPERATURE_BASE_C + random.uniform(-TEMPERATURE_VARIATION_C, TEMPERATURE_VARIATION_C), 1
        ),
        "humidity": round(
            HUMIDITY_BASE_PERCENT + random.uniform(-HUMIDITY_VARIATION_PERCENT, HUMIDITY_VARIATION_PERCENT), 1
        ),
        "luminosity": round(
            max(0.0, LUMINOSITY_BASE_LUX + random.uniform(-LUMINOSITY_VARIATION_LUX, LUMINOSITY_VARIATION_LUX)),
            1,
        ),
    }


def build_client(config: SimulatorConfig) -> mqtt.Client:
    status_topic = f"{TOPIC_PREFIX}/{config.room_id}/{config.device_id}/status"

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"{config.device_id}-simulator",
    )
    client.username_pw_set(config.username, config.password)
    client.will_set(status_topic, payload="offline", qos=1, retain=True)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"Conectado ao broker {config.host}:{config.port}")
            client.publish(status_topic, payload="online", qos=1, retain=True)
        else:
            print(f"Falha ao conectar: {reason_code}")

    def on_disconnect(client: mqtt.Client, userdata, flags, reason_code, properties):
        print(f"Desconectado do broker (reason_code={reason_code})")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    return client


def main() -> int:
    config = parse_args()
    telemetry_topic = f"{TOPIC_PREFIX}/{config.room_id}/{config.device_id}/telemetry"
    status_topic = f"{TOPIC_PREFIX}/{config.room_id}/{config.device_id}/status"

    client = build_client(config)
    client.connect(config.host, config.port, keepalive=60)
    client.loop_start()

    running = True

    def handle_shutdown(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print(
        f"Simulando dispositivo {config.device_id} (sala {config.room_id}), "
        f"publicando a cada {config.interval_seconds}s. Ctrl+C para parar."
    )

    try:
        while running:
            reading = build_reading(config)
            payload = json.dumps(reading)
            client.publish(telemetry_topic, payload=payload, qos=1)
            print(f"publish {telemetry_topic} -> {payload}")
            time.sleep(config.interval_seconds)
    finally:
        client.publish(status_topic, payload="offline", qos=1, retain=True)
        client.loop_stop()
        client.disconnect()
        print("Simulador encerrado.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
