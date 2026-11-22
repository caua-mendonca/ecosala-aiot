"""Engenharia de atributos ÚNICA, usada no treino e na inferência em tempo real.

Regras:
- as janelas olham só para o passado (rolling termina na amostra atual);
- valores absurdos viram NaN e são preenchidos com o último valor válido
  (forward fill = passado), nunca com valores futuros;
- o mesmo código roda sobre milhões de linhas (treino, agrupado por
  equipamento) e sobre o buffer das últimas leituras de um equipamento
  (inferência).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RAW_COLUMNS = ["vibration", "current", "temperature", "ambient_temp", "load", "running"]
SHORT = 6    # 6 amostras de 10 min = 1 h
MID = 36     # 36 amostras de 10 min = 6 h
LONG = 144   # 144 amostras de 10 min = 24 h
HISTORY_NEEDED = LONG

PHYSICAL_RANGES = {
    "vibration": (0.0, 40.0),
    "current": (0.0, 40.0),
    "temperature": (-10.0, 140.0),
    "ambient_temp": (-15.0, 55.0),
    "load": (0.0, 1.0),
    "running": (0.0, 1.0),
}
DEFAULTS = {"vibration": 1.3, "current": 6.0, "temperature": 60.0, "ambient_temp": 25.0,
            "load": 0.5, "running": 1.0}

FEATURE_COLUMNS = [
    "vibration", "current", "temperature", "ambient_temp", "load", "running",
    "vib_mean_s", "vib_mean_l", "vib_std_l", "vib_max_l", "vib_trend",
    "cur_mean_s", "cur_mean_l", "cur_std_l", "cur_max_l", "cur_trend",
    "tmp_mean_s", "tmp_mean_l", "tmp_std_l", "tmp_max_l", "tmp_trend",
    "tmp_resid_l", "cur_resid_l", "vib_resid_l", "tmp_resid_m", "cur_resid_m", "vib_resid_m",
    "run_frac_l",
]


def clean(df: pd.DataFrame, group_col: str | None = None) -> pd.DataFrame:
    out = df.copy()
    for col, (lo, hi) in PHYSICAL_RANGES.items():
        s = pd.to_numeric(out[col], errors="coerce")
        out[col] = s.where((s >= lo) & (s <= hi))
    cols = list(PHYSICAL_RANGES)
    if group_col:
        out[cols] = out.groupby(group_col, sort=False)[cols].ffill()
    else:
        out[cols] = out[cols].ffill()
    return out.fillna(DEFAULTS)


def _roll(df: pd.DataFrame, col: str, window: int, how: str, group_col: str | None) -> pd.Series:
    if group_col:
        r = df.groupby(group_col, sort=False)[col].rolling(window, min_periods=1)
        res = getattr(r, how)()
        return res.reset_index(level=0, drop=True).reindex(df.index)
    return getattr(df[col].rolling(window, min_periods=1), how)()


def compute_features(df: pd.DataFrame, group_col: str | None = None) -> pd.DataFrame:
    """Recebe leituras em ordem temporal (por equipamento) e devolve FEATURE_COLUMNS."""
    d = clean(df[RAW_COLUMNS + ([group_col] if group_col else [])], group_col)
    run = d["running"]
    # resíduos: quanto a leitura está acima do esperado para a carga/ambiente atuais
    d["tmp_resid"] = (d["temperature"] - (55.0 + 14.0 * d["load"] + 0.6 * (d["ambient_temp"] - 25.0))) * run
    d["cur_resid"] = (d["current"] - (4.2 + 6.0 * d["load"] + 0.08 * (d["ambient_temp"] - 25.0))) * run
    d["vib_resid"] = (d["vibration"] - (1.3 + 0.7 * d["load"])) * run
    f = pd.DataFrame(index=d.index)
    for c in RAW_COLUMNS:
        f[c] = d[c]
    for src, p in (("vibration", "vib"), ("current", "cur"), ("temperature", "tmp")):
        f[f"{p}_mean_s"] = _roll(d, src, SHORT, "mean", group_col)
        f[f"{p}_mean_l"] = _roll(d, src, LONG, "mean", group_col)
        f[f"{p}_std_l"] = _roll(d, src, LONG, "std", group_col).fillna(0.0)
        f[f"{p}_max_l"] = _roll(d, src, LONG, "max", group_col)
        f[f"{p}_trend"] = f[f"{p}_mean_s"] - f[f"{p}_mean_l"]
    # média dos resíduos só nos instantes em que o compressor estava ligado
    run_l = _roll(d, "running", LONG, "sum", group_col).clip(lower=1.0)
    run_m = _roll(d, "running", MID, "sum", group_col).clip(lower=1.0)
    for p in ("tmp", "cur", "vib"):
        f[f"{p}_resid_l"] = _roll(d, f"{p}_resid", LONG, "sum", group_col) / run_l
        f[f"{p}_resid_m"] = _roll(d, f"{p}_resid", MID, "sum", group_col) / run_m
    f["run_frac_l"] = _roll(d, "running", LONG, "mean", group_col)
    return f[FEATURE_COLUMNS].astype(np.float32)
