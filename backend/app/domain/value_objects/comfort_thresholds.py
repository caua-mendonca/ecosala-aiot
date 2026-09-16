from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComfortThresholds:
    temperature_min_c: float
    temperature_max_c: float
    humidity_min_percent: float
    humidity_max_percent: float
    luminosity_min_lux: float
    temperature_critical_margin_c: float
    humidity_critical_margin_percent: float
    luminosity_critical_margin_lux: float
