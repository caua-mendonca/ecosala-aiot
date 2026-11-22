"""Modelo físico do ar-condicionado (equipamento monitorado).

O MESMO código gera as leituras no simulador em tempo real e no gerador de
dados sintéticos massivos, para que o modelo treinado com dados sintéticos
reconheça o comportamento do equipamento ao vivo.

Variáveis medidas (sobem quando o equipamento degrada):
  vibration  [mm/s RMS]  vibração do compressor
  current    [A]         corrente elétrica
  temperature[°C]        temperatura de descarga do compressor
Variáveis de contexto: ambient_temp [°C], load [0..1], running [0/1]
"""
from __future__ import annotations

import numpy as np

MECHANICAL_MODES = ["rolamento", "superaquecimento", "entupimento", "desbalanceamento"]
SENSOR_MODES = ["deriva_sensor", "travamento_sensor"]
ALL_MODES = MECHANICAL_MODES + SENSOR_MODES

# efeito máximo (d = 1) de cada modo em (vibração, corrente, temperatura)
_MODE_EFFECT = {
    "rolamento": (6.0, 0.9, 7.0),
    "superaquecimento": (1.2, 1.6, 28.0),
    "entupimento": (1.0, 4.0, 13.0),
    "desbalanceamento": (4.5, 0.7, 4.0),
}
_MODE_EXP = {"rolamento": 1.6, "superaquecimento": 1.3, "entupimento": 1.2, "desbalanceamento": 1.1}


def machine_profile(rng: np.random.Generator) -> dict[str, float]:
    """Variação de fábrica entre máquinas (gera sobreposição entre saudáveis e doentes)."""
    return {
        "vib_base": float(rng.normal(1.3, 0.18)),
        "cur_base": float(rng.normal(4.2, 0.3)),
        "temp_base": float(rng.normal(55.0, 2.0)),
    }


def equipment_readings(
    degradation: np.ndarray,
    mode: str | None,
    ambient: np.ndarray,
    load: np.ndarray,
    running: np.ndarray,
    profile: dict[str, float],
    noise: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calcula vibração, corrente e temperatura (vetorizado com numpy)."""
    d = np.clip(degradation, 0.0, 1.0)
    n = d.shape[0]
    vib = profile["vib_base"] + 0.7 * load
    cur = profile["cur_base"] + 6.0 * load + 0.08 * (ambient - 25.0)
    tmp = profile["temp_base"] + 14.0 * load + 0.6 * (ambient - 25.0)
    if mode in _MODE_EFFECT:
        ev, ec, et = _MODE_EFFECT[mode]
        dp = d ** _MODE_EXP[mode]
        vib = vib + ev * dp
        cur = cur + ec * dp
        tmp = tmp + et * dp
        if mode == "desbalanceamento":
            vib = vib + 1.2 * dp * np.abs(np.sin(np.arange(n) * 0.7))
    vib = vib + rng.normal(0, 0.25 * noise, n) * (1 + d)
    cur = cur + rng.normal(0, 0.35 * noise, n)
    tmp = tmp + rng.normal(0, 1.5 * noise, n)
    off = running < 0.5
    vib = np.where(off, np.abs(rng.normal(0.05, 0.03, n)), vib)
    cur = np.where(off, np.abs(rng.normal(0.15, 0.05, n)), cur)
    tmp = np.where(off, ambient + 3.0 + rng.normal(0, 0.8 * noise, n), tmp)
    return np.maximum(vib, 0.0), np.maximum(cur, 0.0), tmp


def health_from_degradation(d: np.ndarray) -> np.ndarray:
    """Índice de saúde 0..100 (rótulo de verdade, nunca enviado em tempo real)."""
    return 100.0 * (1.0 - np.clip(d, 0.0, 1.0) ** 0.8)


def degradation_curve(t: np.ndarray, onset: float, failure: float) -> np.ndarray:
    """Degradação progressiva entre o início (onset) e a falha (failure)."""
    span = max(failure - onset, 1e-6)
    x = np.clip((t - onset) / span, 0.0, 1.0)
    return x ** 1.4
