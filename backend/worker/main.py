"""Worker de jobs demorados (Laboratório de Dados e Treinamento).

Consome as filas q.jobs.generate e q.jobs.train, uma tarefa por vez, em uma
thread separada para não perder o heartbeat do RabbitMQ. O progresso é
publicado em ecosala.events (job.progress / job.done / job.failed) e chega à
interface pelo WebSocket. A API nunca fica travada esperando.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import numpy as np

from ecosala_common import ml, synthetic
from ecosala_common import topology as T
from ecosala_common.config import (DATA_DIR, INFLUX_LAB_BUCKET, INFLUX_ORG, INFLUX_URL, MODELS_DIR,
                                   SAMPLE_MINUTES, env, env_bool)
from ecosala_common.envelope import decode, make_envelope
from ecosala_common.health import beat
from ecosala_common.rabbit import connect, publish

log = logging.getLogger("worker")
DATASETS = os.path.join(DATA_DIR, "datasets")


class JobRunner:
    def __init__(self) -> None:
        self.conn = None
        self.ch = None

    # publica de forma segura a partir da thread do job
    def emit(self, type_: str, job_id: str, payload: dict) -> None:
        envelope = make_envelope(type_, None, {"job_id": job_id, **payload})
        rk = type_ if type_ == "model.updated" else f"{type_}.{job_id}"

        def _do() -> None:
            publish(self.ch, T.EX_EVENTS, rk, envelope)
        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            self.conn.add_callback_threadsafe(_do)

    def progress_cb(self, job_id: str, kind: str):  # noqa: ANN201
        last = {"t": 0.0}

        def cb(p: float, message: str) -> None:
            if time.time() - last["t"] > 0.4 or p >= 1.0:
                last["t"] = time.time()
                self.emit("job.progress", job_id, {"kind": kind, "progress": round(p, 3), "message": message})
        return cb

    # ------------------------------------------------------------ geração
    def run_generate(self, job_id: str, params: dict) -> dict:
        allowed = set(synthetic.SynthConfig.__dataclass_fields__)
        cfg = synthetic.SynthConfig(**{k: v for k, v in params.items() if k in allowed and k != "sample_minutes"},
                                    sample_minutes=SAMPLE_MINUTES)
        out_dir = os.path.join(DATASETS, job_id)
        cb = self.progress_cb(job_id, "generate")
        summary = synthetic.generate(cfg, out_dir, progress=lambda p, m: cb(0.9 * p, m))
        cb(0.92, "gravando amostra no bucket 'lab' do InfluxDB")
        try:
            summary["influx_sample_points"] = write_lab_sample(out_dir, job_id)
        except Exception as exc:  # noqa: BLE001 - amostra é opcional
            log.warning("não foi possível gravar amostra no InfluxDB: %s", exc)
            summary["influx_sample_points"] = 0
        summary["dataset_id"] = job_id
        summary["size_mb"] = round(sum(os.path.getsize(os.path.join(out_dir, f)) for f in os.listdir(out_dir)) / 1e6, 1)
        with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
        cb(1.0, "concluído")
        return summary

    # --------------------------------------------------------------- treino
    def run_train(self, job_id: str, params: dict) -> dict:
        dataset = params.get("dataset_id") or latest_dataset()
        if not dataset:
            raise RuntimeError("nenhum dataset gerado ainda; use o Laboratório de Dados primeiro")
        path = os.path.join(DATASETS, os.path.basename(dataset))
        if not os.path.isfile(os.path.join(path, "meta.json")):
            raise RuntimeError(f"dataset não encontrado: {dataset}")
        version = ml.next_version(MODELS_DIR)
        result = ml.train(path, MODELS_DIR, version, progress=self.progress_cb(job_id, "train"),
                          max_train_rows=int(params.get("max_train_rows", 600_000)))
        active = ml.load_active(MODELS_DIR)
        result["activated"] = bool(active and active.version == version)
        result.pop("equipment_split", None)
        self.emit("model.updated", job_id, {"version": version, "activated": result["activated"],
                                            "valid": result["valid"], "result": result})
        return result

    def execute(self, job_id: str, kind: str, params: dict) -> None:
        self.emit("job.progress", job_id, {"kind": kind, "progress": 0.0, "message": "iniciado",
                                           "params": params})
        try:
            result = self.run_generate(job_id, params) if kind == "generate" else self.run_train(job_id, params)
            self.emit("job.done", job_id, {"kind": kind, "progress": 1.0, "result": result})
            log.info("job %s (%s) concluído", job_id, kind)
        except Exception as exc:  # noqa: BLE001
            log.exception("job %s falhou", job_id)
            self.emit("job.failed", job_id, {"kind": kind, "error": str(exc)})

    # ----------------------------------------------------------------- loop
    def serve(self) -> None:
        while True:
            self.conn = connect()
            self.ch = self.conn.channel()
            self.ch.basic_qos(prefetch_count=1)
            self.maybe_bootstrap()
            busy = {"thread": None, "tag": None}

            def on_job(chan, method, props, body):  # noqa: ANN001
                try:
                    msg = decode(body)
                    p = msg["payload"]
                    kind = "generate" if method.routing_key == "job.generate" else "train"
                    t = threading.Thread(target=self.execute, args=(p["job_id"], kind, p.get("params") or {}),
                                         daemon=True)
                    busy["thread"], busy["tag"] = t, method.delivery_tag
                    t.start()
                except Exception:  # noqa: BLE001
                    log.exception("pedido de job inválido -> DLQ")
                    chan.basic_nack(method.delivery_tag, requeue=False)

            for q in (T.Q_JOB_GENERATE, T.Q_JOB_TRAIN):
                self.ch.basic_consume(q, on_job)
            log.info("aguardando jobs em %s e %s", T.Q_JOB_GENERATE, T.Q_JOB_TRAIN)
            try:
                while True:
                    self.conn.process_data_events(time_limit=0.2)
                    beat()
                    t = busy["thread"]
                    if t is not None and not t.is_alive():
                        self.ch.basic_ack(busy["tag"])
                        busy["thread"], busy["tag"] = None, None
            except Exception as exc:  # noqa: BLE001
                log.warning("conexão perdida (%s); reconectando", exc)
                time.sleep(2)

    def maybe_bootstrap(self) -> None:
        """Na primeira subida, gera um dataset pequeno e treina a versão 1."""
        if not env_bool("AUTO_BOOTSTRAP_MODEL", True) or ml.load_active(MODELS_DIR) is not None:
            return
        if getattr(self, "_bootstrapping", False):
            return
        self._bootstrapping = True
        job_gen = f"bootstrap-gen-{uuid.uuid4().hex[:6]}"
        job_train = f"bootstrap-train-{uuid.uuid4().hex[:6]}"

        def run() -> None:
            log.info("nenhum modelo encontrado: treino automático inicial")
            self.execute(job_gen, "generate", {"n_equipment": 60, "days": 60, "seed": 2026})
            self.execute(job_train, "train", {"dataset_id": job_gen})
        threading.Thread(target=run, daemon=True).start()


def latest_dataset() -> str | None:
    if not os.path.isdir(DATASETS):
        return None
    ds = [d for d in os.listdir(DATASETS) if os.path.isfile(os.path.join(DATASETS, d, "meta.json"))]
    return max(ds, key=lambda d: os.path.getmtime(os.path.join(DATASETS, d, "meta.json")), default=None)


def write_lab_sample(out_dir: str, job_id: str, max_points: int = 40000) -> int:
    """Grava uma amostra do dataset no bucket separado 'lab' (não mistura com dados ao vivo)."""
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS

    data = synthetic.load_equipment(out_dir)
    equips = np.unique(data["equipment"])[:3]
    # só os últimos 20 dias de cada equipamento (o bucket 'lab' tem retenção de 30 dias)
    last = int(20 * 1440 / SAMPLE_MINUTES)
    idx = np.concatenate([np.nonzero(data["equipment"] == e)[0][-last:] for e in equips])[:max_points]
    tmax = {int(e): int(data["t"][data["equipment"] == e].max()) for e in equips}
    now = datetime.now(UTC)
    points = []
    for i in idx:
        pt = Point("synthetic_equipment").tag("dataset", job_id).tag("equipment", f"eq-{int(data['equipment'][i])}")
        for f in ("vibration", "current", "temperature"):
            v = float(data[f][i])
            if np.isfinite(v):
                pt = pt.field(f, v)
        pt = pt.field("rul_h", float(data["rul_h"][i])).field("health", float(data["health"][i]))
        back = tmax[int(data["equipment"][i])] - int(data["t"][i])
        points.append(pt.time(now - timedelta(minutes=SAMPLE_MINUTES * back), WritePrecision.S))
    with InfluxDBClient(url=INFLUX_URL, token=env("INFLUXDB_TOKEN"), org=INFLUX_ORG, timeout=60000) as cli:
        w = cli.write_api(write_options=SYNCHRONOUS)
        for k in range(0, len(points), 5000):
            w.write(bucket=INFLUX_LAB_BUCKET, org=INFLUX_ORG, record=points[k:k + 5000])
    return len(points)


def cleanup_old_datasets(keep: int = 5) -> None:
    if not os.path.isdir(DATASETS):
        return
    ds = sorted(os.listdir(DATASETS), key=lambda d: os.path.getmtime(os.path.join(DATASETS, d)))
    for d in ds[:-keep]:
        shutil.rmtree(os.path.join(DATASETS, d), ignore_errors=True)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    os.makedirs(DATASETS, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)
    cleanup_old_datasets()
    JobRunner().serve()


if __name__ == "__main__":
    main()
