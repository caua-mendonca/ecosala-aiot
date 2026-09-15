from __future__ import annotations

from enum import StrEnum


class ComfortStatus(StrEnum):
    """Classificacao do conforto ambiental de uma leitura."""

    OK = "OK"
    ATENCAO = "ATENCAO"
    CRITICO = "CRITICO"
