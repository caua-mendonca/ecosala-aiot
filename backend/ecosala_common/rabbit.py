"""Utilidades para os serviços que usam pika (cliente AMQP síncrono)."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel

from .health import beat
from .config import RABBIT_HOST, RABBIT_PORT, RABBIT_VHOST, env
from .envelope import InvalidEnvelope, decode, encode

log = logging.getLogger("rabbit")


def connect(user_env: str = "RABBITMQ_USER", pass_env: str = "RABBITMQ_PASSWORD",
            heartbeat: int = 60) -> pika.BlockingConnection:
    params = pika.ConnectionParameters(
        host=RABBIT_HOST, port=RABBIT_PORT, virtual_host=RABBIT_VHOST,
        credentials=pika.PlainCredentials(env(user_env), env(pass_env)),
        heartbeat=heartbeat, blocked_connection_timeout=60,
        client_properties={"connection_name": env(user_env)},
    )
    while True:
        try:
            return pika.BlockingConnection(params)
        except Exception as exc:  # noqa: BLE001 - broker ainda subindo
            log.warning("RabbitMQ indisponível (%s); tentando de novo em 3s", exc)
            time.sleep(3)


def publish(channel: BlockingChannel, exchange: str, routing_key: str, envelope: dict) -> None:
    channel.basic_publish(
        exchange=exchange, routing_key=routing_key, body=encode(envelope),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2,
                                        message_id=envelope["id"], type=envelope["type"]),
    )


def consume_forever(queue: str, handler: Callable[[BlockingChannel, dict, str], None],
                    prefetch: int = 50, user_env: str = "RABBITMQ_USER",
                    pass_env: str = "RABBITMQ_PASSWORD") -> None:
    """Consome uma fila. Erro no processamento => nack sem requeue => DLQ."""
    while True:
        conn = connect(user_env, pass_env)
        ch = conn.channel()
        ch.basic_qos(prefetch_count=prefetch)

        def _cb(chan, method, props, body):  # noqa: ANN001
            try:
                msg = decode(body)
                handler(chan, msg, method.routing_key)
                chan.basic_ack(method.delivery_tag)
            except InvalidEnvelope as exc:
                log.warning("mensagem inválida -> DLQ: %s", exc)
                chan.basic_nack(method.delivery_tag, requeue=False)
            except Exception:  # noqa: BLE001
                log.exception("falha ao processar mensagem -> DLQ")
                chan.basic_nack(method.delivery_tag, requeue=False)

        ch.basic_consume(queue=queue, on_message_callback=_cb)
        log.info("consumindo fila %s", queue)
        try:
            while True:
                conn.process_data_events(time_limit=1)
                beat()
        except Exception as exc:  # noqa: BLE001
            log.warning("conexão com RabbitMQ perdida (%s); reconectando", exc)
            time.sleep(2)
