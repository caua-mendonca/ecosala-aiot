"""PostgreSQL: usuários, dispositivos, configurações, regras, alertas, jobs, modelos e auditoria."""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from typing import Any

import bcrypt
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from ecosala_common import catalog

from . import settings

log = logging.getLogger("api.db")
_pool: ConnectionPool | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('viewer','operator','admin')),
    failed_attempts INT NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    room TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('sensor','actuator','equipment')),
    type TEXT NOT NULL,
    unit TEXT,
    normal_min DOUBLE PRECISION,
    normal_max DOUBLE PRECISION,
    controllable BOOLEAN NOT NULL DEFAULT FALSE,
    node TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rules (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    source_device TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    operator TEXT NOT NULL CHECK (operator IN ('>','<','alert')),
    threshold DOUBLE PRECISION NOT NULL DEFAULT 0,
    hysteresis DOUBLE PRECISION NOT NULL DEFAULT 0,
    actuator_device TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    device TEXT NOT NULL,
    room TEXT,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    health DOUBLE PRECISION,
    rul_h DOUBLE PRECISION,
    state TEXT NOT NULL DEFAULT 'open',
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS alerts_state_idx ON alerts(state);
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    username TEXT,
    action TEXT NOT NULL,
    target TEXT,
    details JSONB
);
CREATE INDEX IF NOT EXISTS audit_ts_idx ON audit_log(ts DESC);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    progress DOUBLE PRECISION NOT NULL DEFAULT 0,
    message TEXT,
    params JSONB,
    result JSONB,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS model_versions (
    version INT PRIMARY KEY,
    job_id TEXT,
    valid BOOLEAN NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

DEFAULT_SETTINGS = {
    "no_data_seconds": 10,
    "health_attention": 70,
    "health_critical": 45,
    "rul_alert_hours": 48,
    "assistant_model": settings.OLLAMA_MODEL,
}


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(settings.DATABASE_URL, min_size=1, max_size=10,
                               kwargs={"row_factory": dict_row, "autocommit": True}, open=True)
    return _pool


@contextmanager
def cursor():  # noqa: ANN201
    with pool().connection() as conn, conn.cursor() as cur:
        yield cur


def query(sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []


def one(sql: str, params: tuple | dict | None = None) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with cursor() as cur:
        cur.execute(sql, params)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode())
    except ValueError:
        return False


def init_db() -> None:
    for attempt in range(60):
        try:
            with psycopg.connect(settings.DATABASE_URL, autocommit=True) as conn:
                conn.execute(SCHEMA)
            break
        except psycopg.OperationalError as exc:
            log.warning("PostgreSQL indisponível (%s), tentativa %d", exc, attempt + 1)
            time.sleep(2)
    else:
        raise RuntimeError("PostgreSQL não respondeu")
    seed()


def seed() -> None:
    for username, role, env_name in settings.DEMO_USERS:
        pwd = os.getenv(env_name)
        if pwd and not one("SELECT id FROM users WHERE username=%s", (username,)):
            execute("INSERT INTO users(username,password_hash,role) VALUES (%s,%s,%s)",
                    (username, hash_password(pwd), role))
            log.info("usuário de demonstração criado: %s (%s)", username, role)
    if not one("SELECT 1 AS x FROM devices LIMIT 1"):
        for d in catalog.default_devices():
            execute("""INSERT INTO devices(id,name,room,kind,type,unit,normal_min,normal_max,controllable,node)
                       VALUES (%(id)s,%(name)s,%(room)s,%(kind)s,%(type)s,%(unit)s,%(normal_min)s,%(normal_max)s,
                               %(controllable)s,%(node)s)""", d)
        for r in catalog.default_rules():
            execute("""INSERT INTO rules(name,source_device,operator,threshold,hysteresis,actuator_device,enabled)
                       VALUES (%(name)s,%(source_device)s,%(operator)s,%(threshold)s,%(hysteresis)s,
                               %(actuator_device)s,%(enabled)s)""", r)
        log.info("catálogo inicial de dispositivos e regras criado")
    for k, v in DEFAULT_SETTINGS.items():
        execute("INSERT INTO settings(key,value) VALUES (%s,%s) ON CONFLICT (key) DO NOTHING", (k, Jsonb(v)))


def audit(username: str | None, action: str, target: str | None = None, details: dict | None = None) -> None:
    try:
        execute("INSERT INTO audit_log(username,action,target,details) VALUES (%s,%s,%s,%s)",
                (username, action, target, Jsonb(json.loads(json.dumps(details or {}, default=str)))))
    except Exception:  # noqa: BLE001 - auditoria nunca derruba a requisição
        log.exception("falha ao gravar auditoria")


J = Jsonb
