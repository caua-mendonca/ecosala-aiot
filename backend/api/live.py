"""Estado ao vivo em memória (alimentado pela fila q.websocket) e hub de WebSockets."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("api.live")


class LiveState:
    def __init__(self) -> None:
        self.latest: dict[str, dict[str, Any]] = {}       # device -> último envelope de telemetria
        self.history: dict[str, deque] = {}               # device -> últimas leituras (mini gráfico)
        self.predictions: dict[str, dict[str, Any]] = {}  # equipamento -> última previsão
        self.status: dict[str, dict[str, Any]] = {}       # nó -> online/offline
        self.jobs: dict[str, dict[str, Any]] = {}
        self.recent: deque = deque(maxlen=60)             # últimas mensagens (página Mensageria)
        self.last_telemetry_at: float = 0.0
        self.received = 0

    def update(self, msg: dict[str, Any], routing_key: str) -> None:
        self.received += 1
        self.recent.appendleft({"routing_key": routing_key, "type": msg.get("type"), "device": msg.get("device"),
                                "ts": msg.get("ts"), "id": msg.get("id"),
                                "payload": json.dumps(msg.get("payload"), ensure_ascii=False)[:300]})
        t, dev = msg.get("type"), msg.get("device")
        if t == "telemetry" and dev:
            self.latest[dev] = msg
            self.last_telemetry_at = time.time()
            p = msg["payload"]
            v = p.get("value") if p.get("kind") == "sensor" else (
                p.get("vibration") if p.get("kind") == "equipment" else (1 if p.get("state") else 0))
            h = self.history.setdefault(dev, deque(maxlen=60))
            h.append([msg["ts"], v])
        elif t == "prediction" and dev:
            self.predictions[dev] = msg
        elif t == "status" and dev:
            self.status[dev] = msg
        elif t and t.startswith("job.") and msg["payload"].get("job_id"):
            self.jobs[msg["payload"]["job_id"]] = msg

    def snapshot(self) -> dict[str, Any]:
        return {
            "latest": self.latest,
            "history": {k: list(v) for k, v in self.history.items()},
            "predictions": self.predictions,
            "status": self.status,
            "last_telemetry_age_s": round(time.time() - self.last_telemetry_at, 1) if self.last_telemetry_at else None,
        }


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def add(self, ws: WebSocket) -> None:
        async with self.lock:
            self.clients.add(ws)

    async def remove(self, ws: WebSocket) -> None:
        async with self.lock:
            self.clients.discard(ws)

    async def broadcast(self, data: dict[str, Any]) -> None:
        if not self.clients:
            return
        text = json.dumps(data, ensure_ascii=False)
        dead = []
        for ws in list(self.clients):
            try:
                await asyncio.wait_for(ws.send_text(text), timeout=2)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.remove(ws)


state = LiveState()
hub = Hub()
