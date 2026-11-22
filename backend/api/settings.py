from __future__ import annotations

import os

from ecosala_common.config import env, env_int

DATABASE_URL = os.getenv("DATABASE_URL", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_EXPIRE_MINUTES = env_int("JWT_EXPIRE_MINUTES", 480)
LOGIN_MAX_ATTEMPTS = env_int("LOGIN_MAX_ATTEMPTS", 5)
LOGIN_LOCK_MINUTES = env_int("LOGIN_LOCK_MINUTES", 5)
ASSISTANT_PER_MINUTE = env_int("ASSISTANT_PER_MINUTE", 6)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
CONSUMERS_ENABLED = os.getenv("API_CONSUMERS_ENABLED", "true") == "true"

DEMO_USERS = [
    ("administrador", "admin", "DEMO_ADMIN_PASSWORD"),
    ("operador", "operator", "DEMO_OPERATOR_PASSWORD"),
    ("visualizador", "viewer", "DEMO_VIEWER_PASSWORD"),
]

ADMIN_LINKS = [
    {"name": "RabbitMQ (gerenciamento)", "url": "http://127.0.0.1:15672", "user_env": "RABBITMQ_ADMIN_USER"},
    {"name": "InfluxDB (Data Explorer)", "url": "http://127.0.0.1:8086", "user_env": "INFLUXDB_ADMIN_USER"},
    {"name": "pgAdmin (PostgreSQL)", "url": "http://127.0.0.1:5050", "user_env": "PGADMIN_EMAIL"},
    {"name": "Documentação da API (Swagger)", "url": "/docs", "user_env": None},
]


def require_secrets() -> None:
    if len(JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET ausente ou curto demais: rode scripts/gerar_segredos.py")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL ausente")
    env("RABBITMQ_API_PASSWORD")
