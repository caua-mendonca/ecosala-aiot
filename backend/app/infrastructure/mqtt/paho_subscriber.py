from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

import paho.mqtt.client as mqtt

from app.application.dto.incoming_reading import IncomingReadingDTO
from app.application.use_cases.ingest_reading import IngestReading
from app.domain.entities.device_connection import DeviceConnection
from app.infrastructure.mqtt.payload_schema import parse_telemetry_payload

logger = logging.getLogger(__name__)

TOPIC_PREFIX = "ecosala/v1"
TELEMETRY_TOPIC_FILTER = f"{TOPIC_PREFIX}/+/+/telemetry"
STATUS_TOPIC_FILTER = f"{TOPIC_PREFIX}/+/+/status"
TELEMETRY_QOS = 1
STATUS_QOS = 1
ONLINE_PAYLOAD = "online"
EXPECTED_TOPIC_SEGMENTS = 5


class PahoMessageSubscriber:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        ingest_reading: IngestReading,
        client_id: str = "ecosala-backend",
        keepalive_seconds: int = 60,
    ) -> None:
        self._host = host
        self._port = port
        self._keepalive_seconds = keepalive_seconds
        self._ingest_reading = ingest_reading

        self._devices: dict[str, DeviceConnection] = {}
        self._devices_lock = threading.Lock()

        self._client: mqtt.Client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        self._client.username_pw_set(username, password)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def start(self) -> None:
        self._client.connect(self._host, self._port, keepalive=self._keepalive_seconds)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def get_known_devices(self) -> list[DeviceConnection]:
        with self._devices_lock:
            return list(self._devices.values())

    def is_connected(self) -> bool:
        return self._client.is_connected()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        connect_flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if not reason_code.is_failure:
            logger.info("Conectado ao broker MQTT %s:%s", self._host, self._port)
            client.subscribe(TELEMETRY_TOPIC_FILTER, qos=TELEMETRY_QOS)
            client.subscribe(STATUS_TOPIC_FILTER, qos=STATUS_QOS)
        else:
            logger.error("Falha ao conectar ao broker MQTT: %s", reason_code)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        logger.warning("Desconectado do broker MQTT (reason_code=%s)", reason_code)

    def _on_message(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        topic_parts = message.topic.split("/")
        if len(topic_parts) != EXPECTED_TOPIC_SEGMENTS or topic_parts[:2] != ["ecosala", "v1"]:
            logger.warning("Topico MQTT fora do contrato, ignorando: %s", message.topic)
            return

        _, _, room_id, device_id, kind = topic_parts

        if kind == "telemetry":
            self._handle_telemetry(device_id, room_id, message.payload)
        elif kind == "status":
            self._handle_status(device_id, room_id, message.payload)

    def _handle_telemetry(self, device_id: str, room_id: str, raw_payload: bytes) -> None:
        payload = parse_telemetry_payload(raw_payload)
        if payload is None:
            return

        dto = IncomingReadingDTO(
            device_id=payload.device_id,
            room_id=payload.room_id,
            timestamp=payload.to_datetime(),
            temperature=payload.temperature,
            humidity=payload.humidity,
            luminosity=payload.luminosity,
        )
        self._ingest_reading.execute(dto)
        self._touch_device(device_id, room_id, online=True)

    def _handle_status(self, device_id: str, room_id: str, raw_payload: bytes) -> None:
        status_text = raw_payload.decode("utf-8", errors="replace").strip()
        self._touch_device(device_id, room_id, online=status_text == ONLINE_PAYLOAD)

    def _touch_device(self, device_id: str, room_id: str, online: bool) -> None:
        with self._devices_lock:
            self._devices[device_id] = DeviceConnection(
                device_id=device_id,
                room_id=room_id,
                online=online,
                last_seen=datetime.now(UTC),
            )
