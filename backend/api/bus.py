"""Integração da API com o RabbitMQ (aio-pika).

Consumidores da API:
  q.websocket -> atualiza o estado ao vivo e entrega aos navegadores (WebSocket)
  q.rules     -> motor de regras (atuador automático)
  q.persist   -> grava alertas, jobs e versões de modelo no PostgreSQL
Publicação:
  ecosala.commands (comandos para os dispositivos), ecosala.jobs (pedidos de job)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from ecosala_common import topology as T
from ecosala_common.config import RABBIT_HOST, RABBIT_PORT, RABBIT_VHOST, env
from ecosala_common.envelope import InvalidEnvelope, decode, encode, make_envelope

from . import db, live
from .rules import RuleEngine

log = logging.getLogger("api.bus")


class Bus:
    def __init__(self) -> None:
        self.conn: aio_pika.abc.AbstractRobustConnection | None = None
        self.pub_channel: aio_pika.abc.AbstractChannel | None = None
        self.consumers: dict[str, dict[str, Any]] = {}
        self.engine = RuleEngine()
        self.connected = False

    async def start(self, consume: bool = True) -> None:
        url = (f"amqp://{env('RABBITMQ_USER')}:{env('RABBITMQ_PASSWORD')}@{RABBIT_HOST}:{RABBIT_PORT}/"
               f"{RABBIT_VHOST}")
        while True:
            try:
                self.conn = await aio_pika.connect_robust(url, client_properties={"connection_name": "api"})
                break
            except Exception as exc:  # noqa: BLE001
                log.warning("RabbitMQ indisponível (%s); tentando de novo", exc)
                await asyncio.sleep(3)
        self.pub_channel = await self.conn.channel()
        self.connected = True
        if consume:
            await self.reload_rules()
            for qname, handler, prefetch in ((T.Q_WEBSOCKET, self._on_ws, 200), (T.Q_RULES, self._on_rules, 50),
                                             (T.Q_PERSIST, self._on_persist, 20)):
                ch = await self.conn.channel()
                await ch.set_qos(prefetch_count=prefetch)
                queue = await ch.get_queue(qname, ensure=False)
                self.consumers[qname] = {"queue": queue, "handler": handler, "tag": None, "paused": False}
                await self.resume(qname)

    async def stop(self) -> None:
        if self.conn:
            await self.conn.close()

    # ------------------------------------------------------------ pausa
    async def pause(self, qname: str) -> None:
        c = self.consumers[qname]
        if c["tag"]:
            await c["queue"].cancel(c["tag"])
        c["tag"], c["paused"] = None, True
        log.info("consumidor %s pausado", qname)

    async def resume(self, qname: str) -> None:
        c = self.consumers[qname]
        if c["tag"] is None:
            c["tag"] = await c["queue"].consume(self._wrap(c["handler"]))
        c["paused"] = False

    def _wrap(self, handler):  # noqa: ANN001, ANN202
        async def cb(message: AbstractIncomingMessage) -> None:
            try:
                msg = decode(message.body)
                await handler(msg, message.routing_key or "")
                await message.ack()
            except InvalidEnvelope as exc:
                log.warning("mensagem inválida -> DLQ: %s", exc)
                await message.reject(requeue=False)
            except Exception:  # noqa: BLE001
                log.exception("erro ao processar mensagem -> DLQ")
                await message.reject(requeue=False)
        return cb

    # ------------------------------------------------------------ publicação
    async def publish(self, exchange: str, routing_key: str, envelope: dict) -> None:
        assert self.pub_channel is not None
        ex = await self.pub_channel.get_exchange(exchange, ensure=False)
        await ex.publish(aio_pika.Message(body=encode(envelope), content_type="application/json",
                                          delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                          message_id=envelope["id"], type=envelope["type"]),
                         routing_key=routing_key)

    async def send_command(self, device: dict, action: str, params: dict | None, issued_by: str) -> dict:
        envelope = make_envelope("command", device["id"], {"action": action, "params": params or {},
                                                           "node": device["node"], "issued_by": issued_by},
                                 room=device["room"])
        await self.publish(T.EX_COMMANDS, T.key("command", device["room"], device["id"]), envelope)
        return envelope

    # ------------------------------------------------------------ handlers
    async def _on_ws(self, msg: dict, rk: str) -> None:
        live.state.update(msg, rk)
        await live.hub.broadcast({"rk": rk, **msg})

    async def reload_rules(self) -> None:
        rows = await asyncio.to_thread(db.query, """SELECT r.*, d.room AS actuator_room, d.node AS actuator_node
                                                    FROM rules r JOIN devices d ON d.id = r.actuator_device""")
        self.engine.load(rows)

    async def _on_rules(self, msg: dict, rk: str) -> None:
        for rule, action, reason in self.engine.evaluate(msg):
            device = {"id": rule["actuator_device"], "room": rule["actuator_room"], "node": rule["actuator_node"]}
            env_ = await self.send_command(device, action, {"rule_id": rule["id"], "reason": reason},
                                           f"regra:{rule['id']}")
            await asyncio.to_thread(db.audit, "motor-de-regras", f"comando.{action}", device["id"],
                                    {"regra": rule["name"], "motivo": reason, "command_id": env_["id"]})
            log.info("regra '%s' -> %s %s (%s)", rule["name"], action, device["id"], reason)

    async def _on_persist(self, msg: dict, rk: str) -> None:
        await asyncio.to_thread(persist_event, msg)


def persist_event(msg: dict) -> None:
    t, p = msg["type"], msg["payload"]
    if t == "alert":
        if p.get("state") == "raised":
            if not db.one("SELECT id FROM alerts WHERE device=%s AND kind=%s AND state='open'",
                          (msg["device"], p.get("kind"))):
                db.execute("""INSERT INTO alerts(device,room,kind,severity,message,health,rul_h)
                              VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                           (msg["device"], msg.get("room"), p.get("kind"), p.get("severity"), p.get("message"),
                            p.get("health"), p.get("rul_h")))
        else:
            db.execute("UPDATE alerts SET state='closed', closed_at=now() WHERE device=%s AND kind=%s AND state='open'",
                       (msg["device"], p.get("kind")))
    elif t.startswith("job."):
        status = {"job.progress": "running", "job.done": "done", "job.failed": "failed"}[t]
        job_id = p["job_id"]
        kind = p.get("kind", "generate")
        db.execute("""INSERT INTO jobs(id,kind,status,progress,message,params,created_by)
                      VALUES (%s,%s,%s,%s,%s,%s,'sistema') ON CONFLICT (id) DO NOTHING""",
                   (job_id, kind, status, p.get("progress", 0), p.get("message"), db.J(p.get("params") or {})))
        if t == "job.progress":
            db.execute("""UPDATE jobs SET status=CASE WHEN status IN ('done','failed') THEN status ELSE 'running' END,
                          progress=%s, message=%s, updated_at=now() WHERE id=%s""",
                       (p.get("progress", 0), p.get("message"), job_id))
        elif t == "job.done":
            db.execute("UPDATE jobs SET status='done', progress=1, message='concluído', result=%s, updated_at=now() "
                       "WHERE id=%s", (db.J(json.loads(json.dumps(p.get("result"), default=str))), job_id))
        else:
            db.execute("UPDATE jobs SET status='failed', message=%s, updated_at=now() WHERE id=%s",
                       (p.get("error"), job_id))
    elif t == "model.updated":
        version = int(p["version"])
        if p.get("activated"):
            db.execute("UPDATE model_versions SET active=FALSE WHERE active")
        db.execute("""INSERT INTO model_versions(version,job_id,valid,active,result) VALUES (%s,%s,%s,%s,%s)
                      ON CONFLICT (version) DO UPDATE SET valid=EXCLUDED.valid, active=EXCLUDED.active,
                      result=EXCLUDED.result""",
                   (version, p.get("job_id"), bool(p.get("valid")), bool(p.get("activated")), db.J(p.get("result"))))


bus = Bus()
