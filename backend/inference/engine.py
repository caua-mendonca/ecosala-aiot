"""Lógica de inferência (sem I/O): buffers, features, previsões e alertas com histerese."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ecosala_common.features import HISTORY_NEEDED, RAW_COLUMNS, compute_features
from ecosala_common.ml import LoadedModel
from ecosala_common.synthetic import RUL_CAP_H

HEALTH_ATTENTION = 70.0
HEALTH_CRITICAL = 45.0
RUL_ALERT_H = 48.0
RAISE_AFTER = 3     # previsões seguidas abaixo do limite para disparar
CLEAR_AFTER = 10    # previsões seguidas acima do limite para limpar
MIN_SAMPLES = 6


@dataclass
class AlertState:
    active: bool = False
    below: int = 0
    above: int = 0


@dataclass
class EquipmentState:
    buffer: deque = field(default_factory=lambda: deque(maxlen=HISTORY_NEEDED))
    health_hist: deque = field(default_factory=lambda: deque(maxlen=30))
    ema_health: float | None = None
    ema_rul: float | None = None
    alerts: dict[str, AlertState] = field(default_factory=lambda: {"health": AlertState(), "rul": AlertState()})


class InferenceEngine:
    def __init__(self, model: LoadedModel | None) -> None:
        self.model = model
        self.states: dict[str, EquipmentState] = {}

    def set_model(self, model: LoadedModel | None) -> None:
        self.model = model

    def process(self, device: str, payload: dict) -> tuple[dict | None, list[dict]]:
        """Recebe uma leitura do equipamento; devolve (previsão, eventos de alerta)."""
        st = self.states.setdefault(device, EquipmentState())
        row = {c: payload.get(c) for c in RAW_COLUMNS}
        row["running"] = 1.0 if payload.get("running") else 0.0
        st.buffer.append(row)
        if self.model is None or len(st.buffer) < MIN_SAMPLES:
            return None, []
        df = pd.DataFrame(list(st.buffer), columns=RAW_COLUMNS)
        feats = compute_features(df)
        pred = self.model.predict(feats)
        health, rul = pred["health"], pred["rul"]
        if payload.get("failed"):
            health, rul = 0.0, 0.0
        a = 0.35
        st.ema_health = health if st.ema_health is None else a * health + (1 - a) * st.ema_health
        st.ema_rul = rul if st.ema_rul is None else a * rul + (1 - a) * st.ema_rul
        st.health_hist.append(st.ema_health)
        trend = 0.0
        if len(st.health_hist) >= 5:
            y = np.array(st.health_hist)
            trend = float(np.polyfit(np.arange(len(y)), y, 1)[0])
        h, r = round(st.ema_health, 1), round(st.ema_rul, 1)
        status = "critico" if h < HEALTH_CRITICAL or r < RUL_ALERT_H / 2 else (
            "atencao" if h < HEALTH_ATTENTION or r < RUL_ALERT_H else "normal")
        prediction = {"health": h, "rul_h": r, "rul_capped": r >= RUL_CAP_H * 0.9, "trend": round(trend, 3),
                      "status": status, "model_version": self.model.version, "failed": bool(payload.get("failed")),
                      "raw_health": round(health, 1), "raw_rul_h": round(rul, 1)}
        events = []
        events += self._hysteresis(st.alerts["health"], h < HEALTH_CRITICAL, "health", device, h, r,
                                   f"Saúde do equipamento em {h:.0f}/100 (limite {HEALTH_CRITICAL:.0f})")
        events += self._hysteresis(st.alerts["rul"], r < RUL_ALERT_H, "rul", device, h, r,
                                   f"Falha prevista em cerca de {r:.0f} h")
        return prediction, events

    @staticmethod
    def _hysteresis(state: AlertState, condition: bool, kind: str, device: str, h: float, r: float,
                    message: str) -> list[dict]:
        if condition:
            state.below += 1
            state.above = 0
            if not state.active and state.below >= RAISE_AFTER:
                state.active = True
                return [{"kind": kind, "state": "raised", "severity": "critico", "message": message,
                         "health": h, "rul_h": r, "device": device}]
        else:
            state.above += 1
            state.below = 0
            if state.active and state.above >= CLEAR_AFTER:
                state.active = False
                return [{"kind": kind, "state": "cleared", "severity": "info",
                         "message": f"Alerta normalizado ({kind})", "health": h, "rul_h": r, "device": device}]
        return []
