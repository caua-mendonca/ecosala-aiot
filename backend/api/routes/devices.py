"""Cadastro de dispositivos, comandos (Web -> IoT), regras, alertas e configurações."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ecosala_common import physics

from .. import db
from ..bus import bus
from ..security import User, current_user, require

router = APIRouter(tags=["dispositivos e regras"])
ID = r"^[a-zA-Z0-9_\-]{1,64}$"


class DeviceIn(BaseModel):
    id: str = Field(pattern=ID)
    name: str = Field(min_length=1, max_length=120)
    room: str = Field(pattern=ID)
    kind: Literal["sensor", "actuator", "equipment"]
    type: str = Field(min_length=1, max_length=40)
    unit: str | None = Field(default=None, max_length=20)
    normal_min: float | None = None
    normal_max: float | None = None
    controllable: bool = False
    node: str = Field(pattern=ID)
    enabled: bool = True


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    unit: str | None = Field(default=None, max_length=20)
    normal_min: float | None = None
    normal_max: float | None = None
    controllable: bool | None = None
    enabled: bool | None = None


@router.get("/devices", summary="Lista dispositivos cadastrados")
def list_devices(_: User = Depends(current_user)) -> list[dict]:
    return db.query("SELECT * FROM devices ORDER BY room, kind, id")


@router.get("/devices/{device_id}", summary="Detalhe de um dispositivo")
def get_device(device_id: str, _: User = Depends(current_user)) -> dict:
    d = db.one("SELECT * FROM devices WHERE id=%s", (device_id,))
    if not d:
        raise HTTPException(404, "dispositivo não encontrado")
    return d


@router.post("/devices", status_code=201, summary="Cadastra dispositivo (administrador)")
def create_device(body: DeviceIn, user: User = Depends(require("admin"))) -> dict:
    if db.one("SELECT id FROM devices WHERE id=%s", (body.id,)):
        raise HTTPException(409, "já existe dispositivo com esse id")
    db.execute("""INSERT INTO devices(id,name,room,kind,type,unit,normal_min,normal_max,controllable,node,enabled)
                  VALUES (%(id)s,%(name)s,%(room)s,%(kind)s,%(type)s,%(unit)s,%(normal_min)s,%(normal_max)s,
                          %(controllable)s,%(node)s,%(enabled)s)""", body.model_dump())
    db.audit(user.username, "dispositivo.criar", body.id, body.model_dump())
    return get_device(body.id, user)


@router.put("/devices/{device_id}", summary="Atualiza dispositivo (administrador)")
def update_device(device_id: str, body: DeviceUpdate, user: User = Depends(require("admin"))) -> dict:
    get_device(device_id, user)
    changes = body.model_dump(exclude_unset=True)
    if changes:
        sets = ", ".join(f"{k}=%({k})s" for k in changes)
        db.execute(f"UPDATE devices SET {sets}, updated_at=now() WHERE id=%(id)s", {**changes, "id": device_id})
        db.audit(user.username, "dispositivo.atualizar", device_id, changes)
    return get_device(device_id, user)


@router.delete("/devices/{device_id}", status_code=204, summary="Remove dispositivo (administrador)")
def delete_device(device_id: str, user: User = Depends(require("admin"))) -> None:
    get_device(device_id, user)
    db.execute("DELETE FROM devices WHERE id=%s", (device_id,))
    db.audit(user.username, "dispositivo.remover", device_id)


class CommandIn(BaseModel):
    action: Literal["on", "off"]


@router.post("/devices/{device_id}/command", summary="Envia comando ao atuador (Web -> IoT, operador)")
async def command(device_id: str, body: CommandIn, user: User = Depends(require("operator"))) -> dict:
    d = await asyncio.to_thread(db.one, "SELECT * FROM devices WHERE id=%s", (device_id,))
    if not d:
        raise HTTPException(404, "dispositivo não encontrado")
    if not d["controllable"] or not d["enabled"]:
        raise HTTPException(400, "dispositivo não é controlável")
    env_ = await bus.send_command(d, body.action, None, user.username)
    await asyncio.to_thread(db.audit, user.username, f"comando.{body.action}", device_id,
                            {"command_id": env_["id"], "origem": "web"})
    return {"command_id": env_["id"], "status": "enviado"}


class FaultIn(BaseModel):
    mode: Literal["rolamento", "superaquecimento", "entupimento", "desbalanceamento"] = "rolamento"
    hours: float = Field(default=36.0, ge=2, le=720)


@router.post("/equipment/{device_id}/fault", summary="Injeta falha no equipamento simulado (operador)")
async def inject_fault(device_id: str, body: FaultIn, user: User = Depends(require("operator"))) -> dict:
    d = await asyncio.to_thread(db.one, "SELECT * FROM devices WHERE id=%s AND kind='equipment'", (device_id,))
    if not d:
        raise HTTPException(404, "equipamento não encontrado")
    env_ = await bus.send_command(d, "inject_fault", body.model_dump(), user.username)
    await asyncio.to_thread(db.audit, user.username, "simulador.injetar_falha", device_id, body.model_dump())
    return {"command_id": env_["id"], "status": "enviado"}


@router.post("/equipment/{device_id}/repair", summary="Repara o equipamento simulado (operador)")
async def repair(device_id: str, user: User = Depends(require("operator"))) -> dict:
    d = await asyncio.to_thread(db.one, "SELECT * FROM devices WHERE id=%s AND kind='equipment'", (device_id,))
    if not d:
        raise HTTPException(404, "equipamento não encontrado")
    env_ = await bus.send_command(d, "repair", None, user.username)
    await asyncio.to_thread(db.audit, user.username, "simulador.reparar", device_id)
    return {"command_id": env_["id"], "status": "enviado"}


@router.post("/simulator/{action}", summary="Pausa/retoma o simulador (operador)")
async def simulator(action: Literal["pause", "resume"], user: User = Depends(require("operator"))) -> dict:
    env_ = await bus.send_command({"id": "simulator", "room": "sim", "node": "simulator"}, action, None,
                                  user.username)
    await asyncio.to_thread(db.audit, user.username, f"simulador.{action}", "simulator")
    return {"command_id": env_["id"], "status": "enviado"}


@router.get("/fault-modes", summary="Modos de falha disponíveis")
def fault_modes(_: User = Depends(current_user)) -> dict:
    return {"mechanical": physics.MECHANICAL_MODES, "sensor": physics.SENSOR_MODES}


# ------------------------------------------------------------------ regras
class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_device: str = Field(pattern=ID)
    operator: Literal[">", "<", "alert"]
    threshold: float = 0
    hysteresis: float = Field(default=0, ge=0)
    actuator_device: str = Field(pattern=ID)
    enabled: bool = True


@router.get("/rules", summary="Lista regras de negócio")
def list_rules(_: User = Depends(current_user)) -> list[dict]:
    return db.query("SELECT * FROM rules ORDER BY id")


@router.post("/rules", status_code=201, summary="Cria regra (administrador)")
async def create_rule(body: RuleIn, user: User = Depends(require("admin"))) -> dict:
    row = await asyncio.to_thread(db.one, """INSERT INTO rules(name,source_device,operator,threshold,hysteresis,
        actuator_device,enabled) VALUES (%(name)s,%(source_device)s,%(operator)s,%(threshold)s,%(hysteresis)s,
        %(actuator_device)s,%(enabled)s) RETURNING *""", body.model_dump())
    await asyncio.to_thread(db.audit, user.username, "regra.criar", str(row["id"]), body.model_dump())
    await bus.reload_rules()
    return row


@router.put("/rules/{rule_id}", summary="Atualiza regra (administrador)")
async def update_rule(rule_id: int, body: RuleIn, user: User = Depends(require("admin"))) -> dict:
    row = await asyncio.to_thread(db.one, """UPDATE rules SET name=%(name)s, source_device=%(source_device)s,
        operator=%(operator)s, threshold=%(threshold)s, hysteresis=%(hysteresis)s,
        actuator_device=%(actuator_device)s, enabled=%(enabled)s WHERE id=%(id)s RETURNING *""",
                                  {**body.model_dump(), "id": rule_id})
    if not row:
        raise HTTPException(404, "regra não encontrada")
    await asyncio.to_thread(db.audit, user.username, "regra.atualizar", str(rule_id), body.model_dump())
    await bus.reload_rules()
    return row


@router.delete("/rules/{rule_id}", status_code=204, summary="Remove regra (administrador)")
async def delete_rule(rule_id: int, user: User = Depends(require("admin"))) -> None:
    await asyncio.to_thread(db.execute, "DELETE FROM rules WHERE id=%s", (rule_id,))
    await asyncio.to_thread(db.audit, user.username, "regra.remover", str(rule_id))
    await bus.reload_rules()


# ------------------------------------------------------------------ alertas
@router.get("/alerts", summary="Alertas (abertos ou histórico)")
def alerts(state: Literal["open", "closed", "all"] = "open", limit: int = 100,
           _: User = Depends(current_user)) -> list[dict]:
    limit = max(1, min(limit, 500))
    if state == "all":
        return db.query("SELECT * FROM alerts ORDER BY opened_at DESC LIMIT %s", (limit,))
    return db.query("SELECT * FROM alerts WHERE state=%s ORDER BY opened_at DESC LIMIT %s", (state, limit))


# ------------------------------------------------------------- configurações
@router.get("/settings", summary="Configurações da aplicação")
def get_settings(_: User = Depends(current_user)) -> dict:
    return {r["key"]: r["value"] for r in db.query("SELECT key, value FROM settings")}


@router.put("/settings/{key}", summary="Altera configuração (administrador)")
def put_setting(key: str, value: dict, user: User = Depends(require("admin"))) -> dict:
    if "value" not in value:
        raise HTTPException(400, "envie {\"value\": ...}")
    db.execute("""INSERT INTO settings(key,value) VALUES (%s,%s)
                  ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now()""",
               (key, db.J(value["value"])))
    db.audit(user.username, "configuracao.alterar", key, value)
    return get_settings(user)
