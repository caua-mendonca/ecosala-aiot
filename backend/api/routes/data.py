"""Leituras (InfluxDB), estado ao vivo e insights da IA."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from .. import db, influx, live
from ..security import User, current_user

router = APIRouter(tags=["leituras e insights"])


@router.get("/live/snapshot", summary="Estado ao vivo (últimas leituras, previsões e status)")
def snapshot(_: User = Depends(current_user)) -> dict:
    return live.state.snapshot()


@router.get("/readings/latest", summary="Última leitura de cada dispositivo (InfluxDB)")
def latest(_: User = Depends(current_user)) -> dict:
    try:
        return influx.latest()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"InfluxDB indisponível: {exc}") from exc


@router.get("/readings/history", summary="Histórico de um dispositivo (InfluxDB)")
def history(device: str, field: str = "value",
            measurement: Literal["sensor", "actuator", "equipment", "prediction"] = "sensor",
            range: Literal["15m", "1h", "6h", "24h", "7d"] = "1h",  # noqa: A002
            _: User = Depends(current_user)) -> dict:
    try:
        points = influx.history(device, measurement, field, range)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"InfluxDB indisponível: {exc}") from exc
    values = [p["value"] for p in points if p["value"] is not None]
    stats = {"count": len(values)}
    if values:
        stats.update(min=min(values), max=max(values), mean=sum(values) / len(values))
    return {"device": device, "field": field, "measurement": measurement, "range": range,
            "points": points, "stats": stats}


@router.get("/insights", summary="Saúde, vida útil restante, tendência e alertas por equipamento")
def insights(_: User = Depends(current_user)) -> dict:
    equipment = db.query("SELECT id, name, room FROM devices WHERE kind='equipment' ORDER BY id")
    open_alerts = db.query("SELECT * FROM alerts WHERE state='open' ORDER BY opened_at DESC")
    model = db.one("SELECT version, valid, created_at FROM model_versions WHERE active ORDER BY version DESC LIMIT 1")
    items = []
    for e in equipment:
        pred = live.state.predictions.get(e["id"])
        tel = live.state.latest.get(e["id"])
        items.append({**e, "prediction": pred["payload"] if pred else None, "prediction_ts": pred["ts"] if pred else None,
                      "telemetry": tel["payload"] if tel else None,
                      "alerts": [a for a in open_alerts if a["device"] == e["id"]]})
    return {"equipment": items, "model": model, "open_alerts": len(open_alerts)}
