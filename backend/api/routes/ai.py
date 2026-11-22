"""Laboratório de Dados, Treinamento, modelos e Assistente (LLM local)."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ecosala_common import physics, synthetic
from ecosala_common import topology as T
from ecosala_common.envelope import make_envelope

from .. import assistant, db
from ..bus import bus
from ..security import User, assistant_limiter, current_user, require

router = APIRouter(tags=["inteligência artificial"])


class GenerateIn(BaseModel):
    n_equipment: int = Field(100, ge=1, le=2000, description="número de equipamentos (1 por sala)")
    sensors_per_type: int = Field(1, ge=1, le=20, description="sensores de cada tipo por sala")
    days: int = Field(90, ge=1, le=1095, description="período simulado em dias")
    failure_pct: float = Field(45, ge=0, le=100)
    failure_modes: list[str] = Field(default_factory=lambda: list(physics.MECHANICAL_MODES))
    sensor_fault_pct: float = Field(8, ge=0, le=100)
    sensor_fault_modes: list[str] = Field(default_factory=lambda: list(physics.SENSOR_MODES))
    noise: float = Field(1.0, ge=0, le=5)
    missing_pct: float = Field(1.0, ge=0, le=100)
    outlier_pct: float = Field(0.3, ge=0, le=100)
    seed: int = Field(42, ge=0, le=2**31 - 1)


@router.get("/lab/defaults", summary="Parâmetros padrão e limites do gerador")
def lab_defaults(_: User = Depends(current_user)) -> dict:
    return {"defaults": GenerateIn().model_dump(), "max_readings": synthetic.MAX_READINGS,
            "mechanical_modes": physics.MECHANICAL_MODES, "sensor_modes": physics.SENSOR_MODES,
            "sample_minutes": synthetic.SynthConfig().sample_minutes}


@router.post("/lab/estimate", summary="Estima o volume de leituras")
def lab_estimate(body: GenerateIn, _: User = Depends(current_user)) -> dict:
    cfg = synthetic.SynthConfig(**body.model_dump())
    try:
        cfg.validate()
        ok, error = True, None
    except ValueError as exc:
        ok, error = False, str(exc)
    return {"total_readings": cfg.total_readings(), "ok": ok, "error": error, "max_readings": synthetic.MAX_READINGS}


async def _enqueue(kind: str, params: dict, user: User) -> dict:
    job_id = f"{kind[:3]}-{uuid.uuid4().hex[:10]}"
    await asyncio.to_thread(db.execute, """INSERT INTO jobs(id,kind,status,progress,message,params,created_by)
        VALUES (%s,%s,'queued',0,'na fila',%s,%s)""", (job_id, kind, db.J(params), user.username))
    env_ = make_envelope("job.request", None, {"job_id": job_id, "kind": kind, "params": params})
    await bus.publish(T.EX_JOBS, f"job.{kind}", env_)
    await asyncio.to_thread(db.audit, user.username, f"job.{kind}", job_id, params)
    return {"job_id": job_id, "status": "queued"}


@router.post("/lab/generate", status_code=202, summary="Dispara geração de dados sintéticos (administrador)")
async def lab_generate(body: GenerateIn, user: User = Depends(require("admin"))) -> dict:
    cfg = synthetic.SynthConfig(**body.model_dump())
    try:
        cfg.validate()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return await _enqueue("generate", asdict(cfg), user)


@router.get("/lab/datasets", summary="Datasets gerados")
def datasets(_: User = Depends(current_user)) -> list[dict]:
    return db.query("""SELECT id, created_at, updated_at, params, result FROM jobs
                       WHERE kind='generate' AND status='done' ORDER BY updated_at DESC""")


@router.get("/jobs", summary="Jobs (geração e treino)")
def jobs(kind: str | None = None, _: User = Depends(current_user)) -> list[dict]:
    if kind:
        return db.query("SELECT * FROM jobs WHERE kind=%s ORDER BY created_at DESC LIMIT 30", (kind,))
    return db.query("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 30")


class TrainIn(BaseModel):
    dataset_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_\-]{1,64}$")
    max_train_rows: int = Field(600_000, ge=10_000, le=5_000_000)


@router.post("/training/train", status_code=202, summary="Dispara treino dos modelos (administrador)")
async def train(body: TrainIn, user: User = Depends(require("admin"))) -> dict:
    if body.dataset_id and not await asyncio.to_thread(
            db.one, "SELECT id FROM jobs WHERE id=%s AND kind='generate' AND status='done'", (body.dataset_id,)):
        raise HTTPException(404, "dataset não encontrado")
    return await _enqueue("train", body.model_dump(), user)


@router.get("/models", summary="Versões de modelo e métricas")
def models(_: User = Depends(current_user)) -> list[dict]:
    return db.query("SELECT version, job_id, valid, active, created_at, result FROM model_versions "
                    "ORDER BY version DESC LIMIT 20")


@router.get("/models/active", summary="Versão em uso")
def active_model(_: User = Depends(current_user)) -> dict:
    m = db.one("SELECT version, job_id, valid, active, created_at, result FROM model_versions WHERE active "
               "ORDER BY version DESC LIMIT 1")
    return m or {"version": None}


# --------------------------------------------------------------- assistente
class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    history: list[dict] = Field(default_factory=list, max_length=8)


@router.get("/assistant/status", summary="Estado do LLM local (Ollama)")
async def assistant_status(_: User = Depends(current_user)) -> dict:
    return await assistant.status()


@router.get("/assistant/context", summary="Resumo de dados enviado ao LLM (transparência)")
def assistant_context(_: User = Depends(current_user)) -> dict:
    return {"context": assistant.build_context()}


@router.post("/assistant/chat", summary="Pergunta ao assistente (resposta em streaming NDJSON)")
async def chat(body: AskIn, user: User = Depends(current_user)) -> StreamingResponse:
    if not assistant_limiter.hit(user.username):
        raise HTTPException(429, f"limite de perguntas por minuto atingido; aguarde "
                                 f"{assistant_limiter.retry_after(user.username)} s")
    await asyncio.to_thread(db.audit, user.username, "assistente.pergunta", None, {"pergunta": body.question})
    gen = assistant.stream_answer(body.question, body.history)
    return StreamingResponse(gen, media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
