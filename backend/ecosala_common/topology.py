"""Topologia do RabbitMQ: exchanges, filas, bindings e permissões por serviço.

É a fonte única usada pelo rabbit-init (que cria tudo) e pelos serviços
(que só publicam/consomem, sem declarar nada).
"""
from __future__ import annotations

EX_TELEMETRY = "ecosala.telemetry"   # topic: telemetry.<zona>.<tipo>.<id>, status.*, ack.*
EX_EVENTS = "ecosala.events"         # topic: prediction.*, alert.*, job.*, model.*
EX_COMMANDS = "ecosala.commands"     # topic: command.<zona>.<id>
EX_JOBS = "ecosala.jobs"             # direct: job.generate, job.train
EX_DLX = "ecosala.dlx"               # fanout: mensagens mortas

Q_INFLUX = "q.influx"
Q_INFERENCE = "q.inference"
Q_WEBSOCKET = "q.websocket"
Q_COMMANDS = "q.commands"
Q_RULES = "q.rules"
Q_PERSIST = "q.persist"
Q_JOB_GENERATE = "q.jobs.generate"
Q_JOB_TRAIN = "q.jobs.train"
Q_DLQ = "q.dlq"

EXCHANGES: list[tuple[str, str]] = [
    (EX_TELEMETRY, "topic"),
    (EX_EVENTS, "topic"),
    (EX_COMMANDS, "topic"),
    (EX_JOBS, "direct"),
    (EX_DLX, "fanout"),
]

# fila -> (argumentos extras, [(exchange, routing key)])
QUEUES: dict[str, tuple[dict, list[tuple[str, str]]]] = {
    Q_INFLUX: ({}, [(EX_TELEMETRY, "telemetry.#"), (EX_EVENTS, "prediction.#")]),
    Q_INFERENCE: ({}, [(EX_TELEMETRY, "telemetry.*.equipment.*"), (EX_EVENTS, "model.updated")]),
    Q_WEBSOCKET: ({"x-max-length": 20000}, [(EX_TELEMETRY, "#"), (EX_EVENTS, "#")]),
    Q_COMMANDS: ({}, [(EX_COMMANDS, "command.#")]),
    Q_RULES: ({}, [(EX_TELEMETRY, "telemetry.*.temperature.*"), (EX_TELEMETRY, "telemetry.*.co2.*"),
                   (EX_EVENTS, "alert.#")]),
    Q_PERSIST: ({}, [(EX_EVENTS, "alert.#"), (EX_EVENTS, "job.#"), (EX_EVENTS, "model.#")]),
    Q_JOB_GENERATE: ({}, [(EX_JOBS, "job.generate")]),
    Q_JOB_TRAIN: ({}, [(EX_JOBS, "job.train")]),
}

DLQ_ARGS = {"x-dead-letter-exchange": EX_DLX}


def _re(*names: str) -> str:
    return "^(" + "|".join(n.replace(".", r"\.") for n in names) + ")$" if names else "^$"


# serviço -> (tags, configure, write, read). Princípio do menor privilégio.
SERVICE_PERMISSIONS: dict[str, tuple[str, str, str, str]] = {
    "gateway": ("", "^$", _re(EX_TELEMETRY), _re(Q_COMMANDS)),
    "writer": ("", "^$", "^$", _re(Q_INFLUX)),
    "inference": ("", "^$", _re(EX_EVENTS), _re(Q_INFERENCE)),
    "worker": ("", "^$", _re(EX_EVENTS), _re(Q_JOB_GENERATE, Q_JOB_TRAIN)),
    "api": ("monitoring", "^$", _re(EX_COMMANDS, EX_JOBS, EX_EVENTS),
            _re(Q_WEBSOCKET, Q_RULES, Q_PERSIST, Q_DLQ)),
}


def telemetry_key(room: str, kind: str, device: str) -> str:
    return f"telemetry.{_safe(room)}.{_safe(kind)}.{_safe(device)}"


def _safe(part: str) -> str:
    return part.replace(".", "_").replace("#", "_").replace("*", "_")


def key(prefix: str, *parts: str) -> str:
    return ".".join([prefix, *(_safe(p) for p in parts)])
