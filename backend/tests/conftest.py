"""Configuração dos testes.

Quando uma biblioteca de infraestrutura (pika, psycopg, aio_pika, bcrypt,
influxdb_client) não está instalada no ambiente de teste, um módulo falso é
registrado para permitir importar o código e testar a lógica pura. Dentro do
container todas as bibliotecas reais existem.
"""
import importlib
import os
import sys
import types
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("JWT_SECRET", "x" * 40)
os.environ.setdefault("DATABASE_URL", "postgresql://teste")
os.environ.setdefault("RABBITMQ_USER", "api")
os.environ.setdefault("RABBITMQ_PASSWORD", "senha")
os.environ.setdefault("RABBITMQ_API_PASSWORD", "senha")
os.environ.setdefault("INFLUXDB_TOKEN", "token")
os.environ.setdefault("MQTT_DEVICE_PASSWORD", "senha")


def _fake(name: str) -> None:
    try:
        importlib.import_module(name)
    except ImportError:
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            mod_name = ".".join(parts[:i])
            if mod_name not in sys.modules:
                m = mock.MagicMock(name=mod_name)
                m.__path__ = []
                m.__spec__ = types.SimpleNamespace(name=mod_name)
                sys.modules[mod_name] = m


for _n in ("pika", "pika.adapters.blocking_connection", "psycopg", "psycopg.rows", "psycopg.types.json",
           "psycopg_pool", "aio_pika", "aio_pika.abc", "bcrypt", "influxdb_client",
           "influxdb_client.client.write_api"):
    _fake(_n)
