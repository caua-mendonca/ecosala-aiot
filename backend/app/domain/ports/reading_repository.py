from __future__ import annotations

from typing import Protocol

from app.domain.entities.evaluated_reading import EvaluatedReading


class ReadingRepository(Protocol):
    """Porta de persistencia e consulta de leituras.

    Implementada pela infraestrutura (InfluxDB, Etapa 5). O dominio e os
    casos de uso dependem apenas desta interface.
    """

    def save(self, evaluated_reading: EvaluatedReading) -> None:
        """Grava uma leitura ja classificada com seu status de conforto."""
        ...

    def get_latest(self, room_id: str | None = None) -> list[EvaluatedReading]:
        """Retorna a ultima leitura conhecida de cada dispositivo.

        Se `room_id` for informado, restringe aos dispositivos daquela sala.
        """
        ...

    def get_history(
        self, device_id: str, start: str, stop: str, window: str
    ) -> list[EvaluatedReading]:
        """Retorna o historico agregado de um dispositivo entre `start` e `stop`.

        `start`/`stop`/`window` seguem a sintaxe de duracao do Flux
        (ex.: "-1h", "now()", "1m").
        """
        ...
