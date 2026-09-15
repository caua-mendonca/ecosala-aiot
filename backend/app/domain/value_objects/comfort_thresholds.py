from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComfortThresholds:
    """Faixas de conforto e margens de tolerancia, injetadas via configuracao.

    Nenhum valor e fixado no dominio (ver backend/.env.example) — isso
    permite ajustar as faixas sem alterar o ComfortEvaluator.
    """

    temperature_min_c: float
    temperature_max_c: float
    humidity_min_percent: float
    humidity_max_percent: float
    luminosity_min_lux: float
    temperature_critical_margin_c: float
    humidity_critical_margin_percent: float
    luminosity_critical_margin_lux: float
