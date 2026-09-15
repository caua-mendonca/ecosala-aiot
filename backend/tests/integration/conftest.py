"""Utilitarios compartilhados pelos testes de integracao.

Estes testes exigem os servicos reais (Mosquitto/InfluxDB) rodando
localmente — ver infra/mosquitto/ e infra/influxdb/setup.md. Quando os
servicos nao estao acessiveis, os testes sao pulados automaticamente (nao
falham), para nao quebrar uma rodada normal de `pytest`.
"""

from __future__ import annotations

import socket

from app.domain.entities.evaluated_reading import EvaluatedReading


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class FakeReadingRepository:
    """Duplicata minima de tests/unit/fakes.py (evita import entre pastas de teste)."""

    def __init__(self) -> None:
        self.saved: list[EvaluatedReading] = []

    def save(self, evaluated_reading: EvaluatedReading) -> None:
        self.saved.append(evaluated_reading)

    def get_latest(self, room_id: str | None = None) -> list[EvaluatedReading]:
        return []

    def get_history(
        self, device_id: str, start: str, stop: str, window: str
    ) -> list[EvaluatedReading]:
        return []
