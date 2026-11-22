from __future__ import annotations

from enum import StrEnum


class ComfortStatus(StrEnum):
    OK = "OK"
    ATENCAO = "ATENCAO"
    CRITICO = "CRITICO"
