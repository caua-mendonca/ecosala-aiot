"""EcoSala AIoT — API (FastAPI): REST + WebSocket + consumidores RabbitMQ."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import db, live, settings
from .bus import bus
from .routes import ai, auth, data, devices, ops
from .security import tickets

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("api")


async def _periodic_rule_reload() -> None:
    while True:
        await asyncio.sleep(30)
        with contextlib.suppress(Exception):
            await bus.reload_rules()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.require_secrets()
    await asyncio.to_thread(db.init_db)
    await bus.start(consume=settings.CONSUMERS_ENABLED)
    task = asyncio.create_task(_periodic_rule_reload())
    log.info("API pronta")
    yield
    task.cancel()
    await bus.stop()


app = FastAPI(
    title="EcoSala AIoT — API",
    version="2.0.0",
    description="Monitoramento de conforto em salas de aula + manutenção preditiva dos ar-condicionados. "
                "Use POST /api/v1/auth/login e clique em **Authorize** com o token.",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)
origin = os.getenv("CORS_ALLOWED_ORIGIN")
if origin:
    app.add_middleware(CORSMiddleware, allow_origins=[origin], allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, devices.router, data.router, ai.router, ops.router):
    app.include_router(r, prefix="/api/v1")


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    ticket = ws.query_params.get("ticket", "")
    user = tickets.consume(ticket)
    if user is None:
        await ws.close(code=4401, reason="ticket inválido ou expirado")
        return
    await ws.accept()
    await ws.send_json({"type": "hello", "user": user.username, "role": user.role,
                        "snapshot": live.state.snapshot()})
    await live.hub.add(ws)
    try:
        while True:
            msg = await ws.receive_text()   # mantém a conexão; o cliente pode mandar "ping"
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await live.hub.remove(ws)
