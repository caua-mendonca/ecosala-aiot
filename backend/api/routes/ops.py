"""Mensageria (RabbitMQ), auditoria, saúde e links de infraestrutura."""
from __future__ import annotations

import asyncio
import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException

from ecosala_common.config import RABBIT_MGMT_URL, RABBIT_VHOST, env

from .. import db, influx, live, settings
from ..bus import bus
from ..security import User, current_user, require

router = APIRouter(tags=["operação"])


def _mgmt() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=RABBIT_MGMT_URL.rstrip("/") + "/api",
                             auth=(env("RABBITMQ_USER"), env("RABBITMQ_PASSWORD")), timeout=5)


def _rate(stats: dict | None, key: str) -> float:
    return round(float(((stats or {}).get(f"{key}_details") or {}).get("rate", 0.0)), 2)


@router.get("/messaging/overview", summary="Filas, taxas, consumidores e últimas mensagens (RabbitMQ)")
async def messaging(_: User = Depends(current_user)) -> dict:
    vh = quote(RABBIT_VHOST, safe="")
    try:
        async with _mgmt() as cli:
            queues = (await cli.get(f"/queues/{vh}")).json()
            consumers = (await cli.get(f"/consumers/{vh}")).json()
            exchanges = (await cli.get(f"/exchanges/{vh}")).json()
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"API de gerenciamento do RabbitMQ indisponível: {exc}") from exc
    q_out = []
    for q in queues if isinstance(queues, list) else []:
        ms = q.get("message_stats") or {}
        q_out.append({"name": q["name"], "messages": q.get("messages", 0), "ready": q.get("messages_ready", 0),
                      "unacked": q.get("messages_unacknowledged", 0), "consumers": q.get("consumers", 0),
                      "publish_rate": _rate(ms, "publish"), "deliver_rate": _rate(ms, "deliver_get"),
                      "ack_rate": _rate(ms, "ack"), "state": q.get("state"),
                      "dead_letter": (q.get("arguments") or {}).get("x-dead-letter-exchange")})
    c_out = [{"queue": c["queue"]["name"], "tag": c.get("consumer_tag"), "prefetch": c.get("prefetch_count"),
              "connection": (c.get("channel_details") or {}).get("connection_name"),
              "user": (c.get("channel_details") or {}).get("user")} for c in (consumers if isinstance(consumers, list) else [])]
    x_out = [{"name": x["name"], "type": x["type"], "publish_in": _rate(x.get("message_stats"), "publish_in"),
              "publish_out": _rate(x.get("message_stats"), "publish_out")}
             for x in (exchanges if isinstance(exchanges, list) else []) if x["name"].startswith("ecosala")]
    return {"queues": sorted(q_out, key=lambda q: q["name"]), "consumers": c_out, "exchanges": x_out,
            "recent": list(live.state.recent)[:40],
            "api_consumers": {k: {"paused": v["paused"]} for k, v in bus.consumers.items()}}


@router.get("/messaging/dlq", summary="Mensagens mortas (sem removê-las da DLQ)")
async def dlq(_: User = Depends(require("operator"))) -> list[dict]:
    vh = quote(RABBIT_VHOST, safe="")
    async with _mgmt() as cli:
        r = await cli.post(f"/queues/{vh}/q.dlq/get", json={"count": 20, "ackmode": "ack_requeue_true",
                                                              "encoding": "auto", "truncate": 2000})
    if r.status_code != 200:
        raise HTTPException(503, f"não foi possível ler a DLQ: {r.text[:200]}")
    out = []
    for m in r.json():
        deaths = (m.get("properties") or {}).get("headers", {}).get("x-death") or [{}]
        out.append({"routing_key": m.get("routing_key"), "payload": m.get("payload"),
                    "reason": deaths[0].get("reason"), "queue": deaths[0].get("queue"),
                    "count": deaths[0].get("count")})
    return out


@router.post("/messaging/test-dlq", summary="Publica uma mensagem inválida para demonstrar a DLQ (operador)")
async def test_dlq(user: User = Depends(require("operator"))) -> dict:
    import aio_pika
    assert bus.pub_channel is not None
    ex = await bus.pub_channel.get_exchange("ecosala.events", ensure=False)
    await ex.publish(aio_pika.Message(body=b'{"mensagem": "sem o formato padrao"}', content_type="application/json"),
                     routing_key="alert.teste.dlq")
    await asyncio.to_thread(db.audit, user.username, "mensageria.teste_dlq", "q.dlq")
    return {"status": "mensagem inválida publicada em alert.teste.dlq (vai para a DLQ)"}


@router.post("/messaging/consumers/{queue}/{action}", summary="Pausa/retoma um consumidor da API (operador)")
async def consumer_action(queue: str, action: str, user: User = Depends(require("operator"))) -> dict:
    if queue not in bus.consumers or action not in ("pause", "resume"):
        raise HTTPException(404, "consumidor ou ação inválida")
    await (bus.pause(queue) if action == "pause" else bus.resume(queue))
    await asyncio.to_thread(db.audit, user.username, f"mensageria.{action}", queue)
    return {"queue": queue, "paused": bus.consumers[queue]["paused"]}


@router.get("/audit", summary="Log de auditoria (administrador)")
def audit(limit: int = 200, action: str | None = None, _: User = Depends(require("admin"))) -> list[dict]:
    limit = max(1, min(limit, 1000))
    if action:
        return db.query("SELECT * FROM audit_log WHERE action LIKE %s ORDER BY ts DESC LIMIT %s",
                        (action + "%", limit))
    return db.query("SELECT * FROM audit_log ORDER BY ts DESC LIMIT %s", (limit,))


@router.get("/infra/links", summary="Links das interfaces de administração (somente 127.0.0.1)")
def links(_: User = Depends(current_user)) -> list[dict]:
    return [{"name": link["name"], "url": link["url"],
             "user": os.getenv(link["user_env"], "") if link["user_env"] else None} for link in settings.ADMIN_LINKS]


@router.get("/health", summary="Saúde da API e dependências")
async def health() -> dict:
    pg = True
    try:
        await asyncio.to_thread(db.one, "SELECT 1 AS ok")
    except Exception:  # noqa: BLE001
        pg = False
    return {"status": "ok" if pg and bus.connected else "degraded", "postgres": pg,
            "rabbitmq": bus.connected, "influxdb": await asyncio.to_thread(influx.ping)}
