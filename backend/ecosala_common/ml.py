"""Treino e carga dos modelos de regressão (manutenção preditiva).

Modelos:
  - rul    : vida útil restante em horas (0..720)
  - health : índice de saúde 0..100
Ambos usam as MESMAS features (ecosala_common.features.compute_features).
Divisão treino/validação/teste POR EQUIPAMENTO (nunca aleatória por linha).
Comparação obrigatória com a base simples (prever sempre a média do treino).
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from . import synthetic
from .features import FEATURE_COLUMNS, compute_features

TARGETS = {
    "rul": {"column": "rul_h", "label": "Vida útil restante (h)", "clip": (0.0, synthetic.RUL_CAP_H)},
    "health": {"column": "health", "label": "Índice de saúde (0-100)", "clip": (0.0, 100.0)},
}


def _metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y, p)),
        "rmse": float(np.sqrt(mean_squared_error(y, p))),
        "r2": float(r2_score(y, p)),
    }


def split_by_equipment(equip_ids: np.ndarray, seed: int,
                       failing: set[int] | None = None) -> dict[str, np.ndarray]:
    """Divide por EQUIPAMENTO (70/15/15), estratificado entre máquinas que falham e não falham."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(equip_ids)
    failing = failing or set()
    groups = [np.array([u for u in uniq if u in failing]), np.array([u for u in uniq if u not in failing])]
    out: dict[str, list] = {"train": [], "val": [], "test": []}
    for g in groups:
        if len(g) == 0:
            continue
        g = g.copy()
        rng.shuffle(g)
        n = len(g)
        n_te = int(round(n * 0.15)) if n >= 3 else 0
        n_va = int(round(n * 0.15)) if n >= 3 else 0
        n_te, n_va = max(n_te, 1 if n >= 3 else 0), max(n_va, 1 if n >= 3 else 0)
        out["test"] += g[:n_te].tolist()
        out["val"] += g[n_te:n_te + n_va].tolist()
        out["train"] += g[n_te + n_va:].tolist()
    return {k: np.array(sorted(v), dtype=np.int64) for k, v in out.items()}


def build_features(data: dict[str, np.ndarray]) -> pd.DataFrame:
    df = pd.DataFrame({k: data[k] for k in ("equipment", "t", "vibration", "current", "temperature",
                                             "ambient_temp", "load", "running", "rul_h", "health")})
    df = df.sort_values(["equipment", "t"], kind="stable").reset_index(drop=True)
    feats = compute_features(df, group_col="equipment")
    feats["equipment"] = df["equipment"].values
    feats["rul_h"] = df["rul_h"].values
    feats["health"] = df["health"].values
    return feats


def train(dataset_dir: str, models_dir: str, version: int,
          progress: Callable[[float, str], None] | None = None,
          max_train_rows: int = 600_000, seed: int = 7) -> dict[str, Any]:
    def step(p: float, msg: str) -> None:
        if progress:
            progress(p, msg)

    t0 = time.time()
    step(0.02, "carregando dataset")
    data = synthetic.load_equipment(dataset_dir)
    step(0.15, f"calculando features de {len(data['t']):,} linhas")
    feats = build_features(data)
    failing = set(feats.loc[feats["rul_h"] < synthetic.RUL_CAP_H, "equipment"].unique().tolist())
    split = split_by_equipment(feats["equipment"].values, seed, failing)
    parts = {name: feats[feats["equipment"].isin(ids)] for name, ids in split.items()}
    rng = np.random.default_rng(seed)
    tr = parts["train"]
    if len(tr) > max_train_rows:
        tr = tr.iloc[np.sort(rng.choice(len(tr), max_train_rows, replace=False))]
    X_tr = tr[FEATURE_COLUMNS].values
    result: dict[str, Any] = {
        "version": version,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset": os.path.basename(dataset_dir.rstrip("/")),
        "features": FEATURE_COLUMNS,
        "rows": {k: int(len(v)) for k, v in parts.items()},
        "rows_used_train": int(len(tr)),
        "equipment_split": {k: [int(x) for x in v] for k, v in split.items()},
        "targets": {},
    }
    models = {}
    for i, (name, spec) in enumerate(TARGETS.items()):
        step(0.3 + 0.3 * i, f"treinando modelo {name}")
        y_tr = tr[spec["column"]].values
        model = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.08, max_leaf_nodes=48,
                                              l2_regularization=1.0, random_state=seed)
        model.fit(X_tr, y_tr)
        base = DummyRegressor(strategy="mean").fit(X_tr, y_tr)
        lo, hi = spec["clip"]
        target_res: dict[str, Any] = {"label": spec["label"], "metrics": {}, "baseline": {}}
        for part in ("val", "test"):
            dfp = parts[part]
            if len(dfp) == 0:
                continue
            Xp, yp = dfp[FEATURE_COLUMNS].values, dfp[spec["column"]].values
            pred = np.clip(model.predict(Xp), lo, hi)
            target_res["metrics"][part] = _metrics(yp, pred)
            target_res["baseline"][part] = _metrics(yp, base.predict(Xp))
        test = parts["test"] if len(parts["test"]) else parts["val"]
        Xt, yt = test[FEATURE_COLUMNS].values, test[spec["column"]].values
        idx = rng.choice(len(test), min(600, len(test)), replace=False)
        pred_s = np.clip(model.predict(Xt[idx]), lo, hi)
        target_res["scatter"] = [[round(float(a), 2), round(float(b), 2)] for a, b in zip(yt[idx], pred_s)]
        step(0.45 + 0.3 * i, f"importância dos atributos ({name})")
        pi_idx = rng.choice(len(test), min(4000, len(test)), replace=False)
        pi = permutation_importance(model, Xt[pi_idx], yt[pi_idx], n_repeats=3, random_state=seed,
                                    scoring="neg_mean_absolute_error")
        imp = sorted(zip(FEATURE_COLUMNS, pi.importances_mean), key=lambda kv: -kv[1])
        target_res["feature_importance"] = [[k, round(float(v), 4)] for k, v in imp[:15]]
        tm, bm = target_res["metrics"].get("test", {}), target_res["baseline"].get("test", {})
        target_res["beats_baseline"] = bool(tm and bm and tm["mae"] < bm["mae"] and tm["r2"] > bm["r2"])
        result["targets"][name] = target_res
        models[name] = model
    result["train_seconds"] = round(time.time() - t0, 1)
    result["valid"] = all(t["beats_baseline"] for t in result["targets"].values())
    step(0.95, "salvando modelos")
    save_bundle(models_dir, version, models, result)
    step(1.0, "concluído")
    return result


def save_bundle(models_dir: str, version: int, models: dict, meta: dict) -> str:
    os.makedirs(models_dir, exist_ok=True)
    path = os.path.join(models_dir, f"model_v{version:04d}.joblib")
    tmp = path + ".tmp"
    joblib.dump({"models": models, "meta": meta}, tmp)
    os.replace(tmp, path)
    with open(os.path.join(models_dir, f"model_v{version:04d}.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)
    if meta.get("valid", False):
        set_active(models_dir, version)
    return path


def set_active(models_dir: str, version: int) -> None:
    tmp = os.path.join(models_dir, "active.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"version": version}, fh)
    os.replace(tmp, os.path.join(models_dir, "active.json"))


def next_version(models_dir: str) -> int:
    if not os.path.isdir(models_dir):
        return 1
    vs = [int(f[7:11]) for f in os.listdir(models_dir) if f.startswith("model_v") and f.endswith(".json")]
    return max(vs, default=0) + 1


@dataclass
class LoadedModel:
    version: int
    models: dict
    meta: dict

    def predict(self, features: pd.DataFrame) -> dict[str, float]:
        X = features[FEATURE_COLUMNS].values[-1:]
        out = {}
        for name, spec in TARGETS.items():
            lo, hi = spec["clip"]
            out[name] = float(np.clip(self.models[name].predict(X)[0], lo, hi))
        return out


def load_active(models_dir: str) -> LoadedModel | None:
    try:
        with open(os.path.join(models_dir, "active.json"), encoding="utf-8") as fh:
            version = int(json.load(fh)["version"])
        bundle = joblib.load(os.path.join(models_dir, f"model_v{version:04d}.joblib"))
        return LoadedModel(version=version, models=bundle["models"], meta=bundle["meta"])
    except (FileNotFoundError, KeyError, ValueError):
        return None
