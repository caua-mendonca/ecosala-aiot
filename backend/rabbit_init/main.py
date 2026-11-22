"""Cria a topologia e os usuários do RabbitMQ pela API de gerenciamento.

Roda uma vez na subida do Compose (serviço rabbit-init). É idempotente.
- vhost 'ecosala'
- um usuário por serviço com permissões mínimas (sem o usuário guest)
- exchanges, filas duráveis com dead-letter para a DLQ e bindings
"""
from __future__ import annotations

import logging
import os
import sys
import time
from urllib.parse import quote

import requests

from ecosala_common import topology as T
from ecosala_common.config import RABBIT_MGMT_URL, RABBIT_VHOST, env

log = logging.getLogger("rabbit-init")


def main() -> int:
    logging.basicConfig(level="INFO", format="%(asctime)s %(name)s %(levelname)s %(message)s")
    s = requests.Session()
    s.auth = (env("RABBITMQ_ADMIN_USER"), env("RABBITMQ_ADMIN_PASSWORD"))
    base = RABBIT_MGMT_URL.rstrip("/") + "/api"
    vh = quote(RABBIT_VHOST, safe="")
    for _ in range(60):
        try:
            if s.get(f"{base}/overview", timeout=5).ok:
                break
        except requests.RequestException:
            pass
        log.info("aguardando RabbitMQ...")
        time.sleep(2)
    else:
        log.error("RabbitMQ não respondeu")
        return 1

    def put(path: str, body: dict) -> None:
        r = s.put(f"{base}{path}", json=body, timeout=10)
        if r.status_code not in (200, 201, 204):
            raise RuntimeError(f"PUT {path} -> {r.status_code} {r.text}")

    def post(path: str, body: dict) -> None:
        r = s.post(f"{base}{path}", json=body, timeout=10)
        if r.status_code not in (200, 201, 204):
            raise RuntimeError(f"POST {path} -> {r.status_code} {r.text}")

    put(f"/vhosts/{vh}", {"description": "EcoSala AIoT"})
    admin = env("RABBITMQ_ADMIN_USER")
    put(f"/permissions/{vh}/{quote(admin)}", {"configure": ".*", "write": ".*", "read": ".*"})
    for service, (tags, conf, write, read) in T.SERVICE_PERMISSIONS.items():
        user = env(f"RABBITMQ_{service.upper()}_USER", service)
        put(f"/users/{quote(user)}", {"password": env(f"RABBITMQ_{service.upper()}_PASSWORD"), "tags": tags})
        put(f"/permissions/{vh}/{quote(user)}", {"configure": conf, "write": write, "read": read})
        log.info("usuário %s: write=%s read=%s", user, write, read)
    # garante que o usuário guest não exista
    s.delete(f"{base}/users/guest", timeout=10)

    for name, kind in T.EXCHANGES:
        put(f"/exchanges/{vh}/{name}", {"type": kind, "durable": True, "auto_delete": False})
    put(f"/queues/{vh}/{T.Q_DLQ}", {"durable": True, "arguments": {"x-queue-type": "classic"}})
    post(f"/bindings/{vh}/e/{T.EX_DLX}/q/{T.Q_DLQ}", {"routing_key": ""})
    for queue, (args, bindings) in T.QUEUES.items():
        put(f"/queues/{vh}/{queue}", {"durable": True, "arguments": {**T.DLQ_ARGS, **args}})
        for exchange, rk in bindings:
            post(f"/bindings/{vh}/e/{exchange}/q/{queue}", {"routing_key": rk})
        log.info("fila %s -> %s", queue, [rk for _, rk in bindings])
    log.info("topologia do RabbitMQ pronta")
    return 0


if __name__ == "__main__":
    sys.exit(main())
