"""Motor de regras de negócio (atuador acionado automaticamente).

Regras com histerese, por exemplo: temperatura > 28 °C liga a ventilação e só
desliga quando cair abaixo de 28 - 1,5 °C. Regras do tipo 'alert' ligam a
sinalização quando a IA dispara um alerta crítico e desligam quando ele limpa.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleEngine:
    rules: list[dict[str, Any]] = field(default_factory=list)
    active: dict[int, bool] = field(default_factory=dict)          # regra -> atuador ligado pela regra?
    alert_kinds: dict[str, set] = field(default_factory=dict)      # equipamento -> alertas ativos
    loaded_at: float = 0.0

    def load(self, rules: list[dict[str, Any]]) -> None:
        self.rules = [r for r in rules if r.get("enabled")]
        self.loaded_at = time.time()

    def _other_active(self, rule: dict[str, Any]) -> bool:
        return any(self.active.get(o["id"]) for o in self.rules
                   if o["id"] != rule["id"] and o["actuator_device"] == rule["actuator_device"])

    def evaluate(self, msg: dict[str, Any]) -> list[tuple[dict[str, Any], str, str]]:
        """Devolve [(regra, ação 'on'|'off', motivo)] para os comandos a enviar."""
        out: list[tuple[dict[str, Any], str, str]] = []
        device, payload = msg.get("device"), msg.get("payload") or {}
        if msg.get("type") == "telemetry" and isinstance(payload.get("value"), (int, float)):
            value = float(payload["value"])
            for r in self.rules:
                if r["source_device"] != device or r["operator"] not in (">", "<"):
                    continue
                th, hy = float(r["threshold"]), float(r["hysteresis"])
                above = value > th if r["operator"] == ">" else value < th
                back = value < th - hy if r["operator"] == ">" else value > th + hy
                prev = self.active.get(r["id"])
                if above and prev is not True:
                    self.active[r["id"]] = True
                    out.append((r, "on", f"{device}={value:g} {r['operator']} {th:g}"))
                elif back and prev is True:
                    self.active[r["id"]] = False
                    if not self._other_active(r):   # outra regra ainda quer o atuador ligado
                        out.append((r, "off", f"{device}={value:g} voltou ao normal"))
                elif back and prev is None:
                    self.active[r["id"]] = False
        elif msg.get("type") == "alert":
            kinds = self.alert_kinds.setdefault(device or "", set())
            before = bool(kinds)
            if payload.get("state") == "raised" and payload.get("severity") == "critico":
                kinds.add(payload.get("kind"))
            elif payload.get("state") == "cleared":
                kinds.discard(payload.get("kind"))
            after = bool(kinds)
            if before != after:
                for r in self.rules:
                    if r["source_device"] == device and r["operator"] == "alert":
                        self.active[r["id"]] = after
                        out.append((r, "on" if after else "off",
                                    payload.get("message") or "alerta da IA"))
        return out
