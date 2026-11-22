"""Formato único das mensagens que trafegam no RabbitMQ.

Toda mensagem é um JSON com: id (identificador), ts (instante ISO-8601 UTC),
type (tipo), device (dispositivo), room (zona) e payload (conteúdo).
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

MESSAGE_TYPES = {
    "telemetry", "status", "command", "command.ack", "prediction", "alert",
    "job.request", "job.progress", "job.done", "job.failed", "model.updated",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_envelope(
    type_: str,
    device: str | None,
    payload: dict[str, Any],
    room: str | None = None,
    ts: str | None = None,
    msg_id: str | None = None,
) -> dict[str, Any]:
    if type_ not in MESSAGE_TYPES:
        raise ValueError(f"tipo de mensagem desconhecido: {type_}")
    return {
        "id": msg_id or uuid.uuid4().hex,
        "ts": ts or now_iso(),
        "type": type_,
        "device": device,
        "room": room,
        "payload": payload,
    }


def encode(envelope: dict[str, Any]) -> bytes:
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class InvalidEnvelope(ValueError):
    pass


def decode(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidEnvelope(f"JSON inválido: {exc}") from exc
    if not isinstance(data, dict):
        raise InvalidEnvelope("mensagem não é um objeto JSON")
    for key in ("id", "ts", "type", "payload"):
        if key not in data:
            raise InvalidEnvelope(f"campo obrigatório ausente: {key}")
    if data["type"] not in MESSAGE_TYPES:
        raise InvalidEnvelope(f"tipo desconhecido: {data['type']}")
    if not isinstance(data["payload"], dict):
        raise InvalidEnvelope("payload deve ser objeto")
    return data
