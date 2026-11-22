"""Configuração comum lida de variáveis de ambiente.

Os segredos chegam pelo arquivo .env (gerado por scripts/gerar_segredos.py e
ignorado pelo Git) e são injetados pelo Docker Compose em cada container.
"""
from __future__ import annotations

import os


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, "true" if default else "false").strip().lower() in {"1", "true", "yes", "sim"}


# Tempo simulado: cada amostra do simulador e do gerador sintético representa
# SAMPLE_MINUTES minutos. Isso mantém treino e inferência na mesma escala.
SAMPLE_MINUTES = env_int("SAMPLE_MINUTES", 10)

RABBIT_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBIT_PORT = env_int("RABBITMQ_PORT", 5672)
RABBIT_VHOST = os.getenv("RABBITMQ_VHOST", "ecosala")
RABBIT_MGMT_URL = os.getenv("RABBITMQ_MGMT_URL", "http://rabbitmq:15672")

INFLUX_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUX_ORG = os.getenv("INFLUXDB_ORG", "ecosala")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "telemetria")
INFLUX_LAB_BUCKET = os.getenv("INFLUXDB_LAB_BUCKET", "lab")

MODELS_DIR = os.getenv("MODELS_DIR", "/models")
DATA_DIR = os.getenv("DATA_DIR", "/data")
