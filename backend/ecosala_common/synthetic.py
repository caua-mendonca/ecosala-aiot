"""Gerador de dados sintéticos massivos (vida inteira dos equipamentos).

- gera em blocos com numpy (vetorizado por equipamento, nunca ponto a ponto);
- ciclo diário (dia/noite, horários de aula) e sazonal (estações do ano);
- degradação progressiva com ruído e variação entre máquinas;
- modos de falha mecânicos + falhas de sensor (deriva e travamento);
- leituras faltantes e valores absurdos (outliers);
- rótulos de verdade (degrading, rul_h, health) apenas nos dados de treino;
- semente aleatória => geração reproduzível;
- teto máximo de leituras para não travar a máquina.
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

import numpy as np

from . import physics

RUL_CAP_H = 168.0           # 7 dias: acima disso o equipamento é considerado "saudável"
MAX_READINGS = int(os.getenv("SYNTH_MAX_READINGS", "40000000"))
ENV_SENSOR_TYPES = ["temperature", "humidity", "luminosity", "co2", "presence"]


@dataclass
class SynthConfig:
    n_equipment: int = 60
    sensors_per_type: int = 1
    days: int = 120
    failure_pct: float = 45.0
    failure_modes: list[str] = field(default_factory=lambda: list(physics.MECHANICAL_MODES))
    sensor_fault_pct: float = 8.0
    sensor_fault_modes: list[str] = field(default_factory=lambda: list(physics.SENSOR_MODES))
    noise: float = 1.0
    missing_pct: float = 1.0
    outlier_pct: float = 0.3
    seed: int = 42
    sample_minutes: int = 10
    min_failure_days: float = 7.0
    max_failure_days: float = 14.0

    def validate(self) -> None:
        if not 1 <= self.n_equipment <= 2000:
            raise ValueError("n_equipment deve estar entre 1 e 2000")
        if not 1 <= self.sensors_per_type <= 20:
            raise ValueError("sensors_per_type deve estar entre 1 e 20")
        if not 1 <= self.days <= 1095:
            raise ValueError("days deve estar entre 1 e 1095")
        for name in ("failure_pct", "sensor_fault_pct", "missing_pct", "outlier_pct"):
            if not 0 <= getattr(self, name) <= 100:
                raise ValueError(f"{name} deve estar entre 0 e 100")
        if not 0 <= self.noise <= 5:
            raise ValueError("noise deve estar entre 0 e 5")
        bad = [m for m in self.failure_modes if m not in physics.MECHANICAL_MODES]
        bad += [m for m in self.sensor_fault_modes if m not in physics.SENSOR_MODES]
        if bad:
            raise ValueError(f"modos de falha desconhecidos: {bad}")
        if self.failure_pct > 0 and not self.failure_modes:
            raise ValueError("escolha ao menos um modo de falha mecânico")
        if self.total_readings() > MAX_READINGS:
            raise ValueError(
                f"volume pedido ({self.total_readings():,} leituras) acima do teto "
                f"({MAX_READINGS:,}). Reduza equipamentos, sensores ou dias.")

    @property
    def samples_per_equipment(self) -> int:
        return int(self.days * 24 * 60 / self.sample_minutes)

    def total_readings(self) -> int:
        # cada linha do equipamento tem 3 variáveis medidas (vibração, corrente, temperatura)
        equip = self.n_equipment * self.samples_per_equipment * 3
        env = self.n_equipment * len(ENV_SENSOR_TYPES) * self.sensors_per_type * self.samples_per_equipment
        return equip + env


def _environment(t_days: np.ndarray, rng: np.random.Generator, noise: float) -> dict[str, np.ndarray]:
    """Ambiente de uma sala ao longo do tempo (ciclo diário e sazonal)."""
    n = t_days.shape[0]
    hour = (t_days * 24.0) % 24.0
    doy = t_days % 365.0
    weekday = (np.floor(t_days) % 7) < 5
    season = 4.5 * np.sin(2 * np.pi * (doy - 20) / 365.0)
    ext = 24.0 + season + 5.0 * np.sin(2 * np.pi * (hour - 9.0) / 24.0) + rng.normal(0, 0.6 * noise, n)
    cloud = np.clip(rng.normal(0.8, 0.15), 0.3, 1.0)
    lux_ext = np.maximum(0.0, np.sin(np.pi * (hour - 6.0) / 12.0)) * 60000.0 * cloud
    in_class = weekday & (((hour >= 7.5) & (hour < 12)) | ((hour >= 13.5) & (hour < 17.5))
                          | ((hour >= 19) & (hour < 22.5)))
    presence = np.where(in_class, rng.poisson(26, n), rng.poisson(0.3, n)).astype(np.float64)
    room_temp = 0.55 * ext + 11.0 + 0.09 * presence + rng.normal(0, 0.4 * noise, n)
    # o ar-condicionado liga nos horários de aula (e às vezes fora deles)
    running = (in_class | (weekday & (hour >= 7) & (hour < 23) & (rng.random(n) < 0.15))).astype(np.float64)
    room_temp = room_temp - running * 3.0
    load = np.clip(running * (0.40 + 0.025 * (ext - 20.0) + 0.006 * presence
                              + rng.normal(0, 0.05 * noise, n)), 0.0, 1.0)
    humidity = np.clip(60.0 - 0.8 * (ext - 24.0) + 0.15 * presence - 6 * running
                       + rng.normal(0, 2.0 * noise, n), 15, 100)
    luminosity = np.clip(lux_ext * 0.01 + np.where(in_class, 380.0, 0.0) + rng.normal(0, 25 * noise, n), 0, None)
    co2 = 420.0 + presence * 28.0 * (1 - 0.3 * running) + rng.normal(0, 30 * noise, n)
    return {"ext": ext, "lux_ext": lux_ext, "presence": presence, "temperature": room_temp,
            "humidity": humidity, "luminosity": luminosity, "co2": co2, "running": running, "load": load}


def _corrupt(arr: np.ndarray, rng: np.random.Generator, missing_pct: float, outlier_pct: float) -> np.ndarray:
    n = arr.shape[0]
    out = arr.astype(np.float64).copy()
    if outlier_pct > 0:
        mask = rng.random(n) < outlier_pct / 100.0
        k = int(mask.sum())
        if k:
            out[mask] = np.where(rng.random(k) < 0.5, -999.0, out[mask] * rng.uniform(5, 12, k) + 50)
    if missing_pct > 0:
        out[rng.random(n) < missing_pct / 100.0] = np.nan
    return out


def generate(cfg: SynthConfig, out_dir: str,
             progress: Callable[[float, str], None] | None = None,
             block_size: int = 10) -> dict:
    """Gera o dataset em out_dir (blocos .npz + meta.json). Retorna o resumo."""
    cfg.validate()
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(cfg.seed)
    n_s = cfg.samples_per_equipment
    t_days = np.arange(n_s) * cfg.sample_minutes / 1440.0
    per_day = 1440 // cfg.sample_minutes

    n_fail = int(round(cfg.n_equipment * cfg.failure_pct / 100.0))
    order = rng.permutation(cfg.n_equipment)
    failing = set(order[:n_fail].tolist())
    n_sf = int(round(cfg.n_equipment * cfg.sensor_fault_pct / 100.0))
    sensor_fault = set(order[n_fail:n_fail + n_sf].tolist()) if cfg.sensor_fault_modes else set()

    total_rows = 0
    env_readings = 0
    failures_by_mode: dict[str, int] = {}
    blocks = math.ceil(cfg.n_equipment / block_size)
    for b in range(blocks):
        cols: dict[str, list[np.ndarray]] = {k: [] for k in (
            "equipment", "t", "vibration", "current", "temperature", "ambient_temp", "load", "running",
            "degrading", "rul_h", "health", "mode")}
        env_cols: dict[str, list[np.ndarray]] = {"equipment": [], "t": [], **{s: [] for s in ENV_SENSOR_TYPES}}
        for e in range(b * block_size, min((b + 1) * block_size, cfg.n_equipment)):
            erng = np.random.default_rng([cfg.seed, e])
            env = _environment(t_days + erng.uniform(0, 365), erng, cfg.noise)
            profile = physics.machine_profile(erng)
            mode_idx = -1
            if e in failing:
                mode = cfg.failure_modes[int(erng.integers(len(cfg.failure_modes)))]
                mode_idx = physics.ALL_MODES.index(mode)
                fail_at = int(erng.uniform(0.3, 0.98) * n_s)
                dur = int(erng.uniform(cfg.min_failure_days, cfg.max_failure_days) * per_day)
                onset = max(0, fail_at - dur)
                n_e = fail_at  # corre até a falha (run-to-failure)
                d = physics.degradation_curve(np.arange(n_e, dtype=np.float64), onset, fail_at)
                rul = np.minimum((fail_at - np.arange(n_e)) * cfg.sample_minutes / 60.0, RUL_CAP_H)
                failures_by_mode[mode] = failures_by_mode.get(mode, 0) + 1
            else:
                mode = None
                n_e = n_s
                d = np.zeros(n_e)
                rul = np.full(n_e, RUL_CAP_H)
            ambient = env["ext"][:n_e]
            load = env["load"][:n_e]
            running = env["running"][:n_e]
            vib, cur, tmp = physics.equipment_readings(d, mode, ambient, load, running, profile, cfg.noise, erng)
            if e in sensor_fault:
                smode = cfg.sensor_fault_modes[int(erng.integers(len(cfg.sensor_fault_modes)))]
                mode_idx = physics.ALL_MODES.index(smode)
                start = int(erng.uniform(0.2, 0.8) * n_e)
                if smode == "deriva_sensor":
                    vib[start:] += np.linspace(0, erng.uniform(1.5, 4.0), n_e - start)
                else:
                    stop = min(n_e, start + int(erng.uniform(1, 6) * per_day))
                    tmp[start:stop] = tmp[start]
            cols["equipment"].append(np.full(n_e, e, dtype=np.int32))
            cols["t"].append(np.arange(n_e, dtype=np.int32))
            cols["vibration"].append(_corrupt(vib, erng, cfg.missing_pct, cfg.outlier_pct).astype(np.float32))
            cols["current"].append(_corrupt(cur, erng, cfg.missing_pct, cfg.outlier_pct).astype(np.float32))
            cols["temperature"].append(_corrupt(tmp, erng, cfg.missing_pct, cfg.outlier_pct).astype(np.float32))
            cols["ambient_temp"].append(ambient.astype(np.float32))
            cols["load"].append(load.astype(np.float32))
            cols["running"].append(running.astype(np.float32))
            cols["degrading"].append((d > 0).astype(np.int8))
            cols["rul_h"].append(rul.astype(np.float32))
            cols["health"].append(physics.health_from_degradation(d).astype(np.float32))
            cols["mode"].append(np.full(n_e, mode_idx, dtype=np.int8))
            total_rows += n_e
            # sensores ambientais da sala (vários por tipo, com ruído próprio)
            for _ in range(cfg.sensors_per_type):
                env_cols["equipment"].append(np.full(n_s, e, dtype=np.int32))
                env_cols["t"].append(np.arange(n_s, dtype=np.int32))
                for s in ENV_SENSOR_TYPES:
                    v = env[s] + erng.normal(0, 0.02 * (np.abs(env[s]).mean() + 1) * cfg.noise, n_s)
                    env_cols[s].append(_corrupt(v, erng, cfg.missing_pct, cfg.outlier_pct).astype(np.float32))
                env_readings += n_s * len(ENV_SENSOR_TYPES)
        np.savez(os.path.join(out_dir, f"equip_{b:04d}.npz"), **{k: np.concatenate(v) for k, v in cols.items()})
        np.savez(os.path.join(out_dir, f"env_{b:04d}.npz"), **{k: np.concatenate(v) for k, v in env_cols.items()})
        if progress:
            progress((b + 1) / blocks, f"bloco {b + 1}/{blocks}")
    summary = {
        "config": asdict(cfg),
        "equipment_rows": total_rows,
        "equipment_readings": total_rows * 3,
        "env_readings": env_readings,
        "total_readings": total_rows * 3 + env_readings,
        "failing_equipment": n_fail,
        "sensor_fault_equipment": len(sensor_fault),
        "failures_by_mode": failures_by_mode,
        "blocks": blocks,
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    return summary


def load_equipment(out_dir: str) -> dict[str, np.ndarray]:
    files = sorted(f for f in os.listdir(out_dir) if f.startswith("equip_") and f.endswith(".npz"))
    parts: dict[str, list[np.ndarray]] = {}
    for f in files:
        with np.load(os.path.join(out_dir, f)) as z:
            for k in z.files:
                parts.setdefault(k, []).append(z[k])
    return {k: np.concatenate(v) for k, v in parts.items()}
