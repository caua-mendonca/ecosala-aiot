import numpy as np
import pandas as pd
import pytest

from ecosala_common import envelope, ml, physics, synthetic, topology
from ecosala_common.features import FEATURE_COLUMNS, compute_features


def test_envelope_roundtrip():
    e = envelope.make_envelope("telemetry", "temp-101", {"value": 1.5}, room="sala-101")
    d = envelope.decode(envelope.encode(e))
    assert d == e
    assert set(d) == {"id", "ts", "type", "device", "room", "payload"}


@pytest.mark.parametrize("body", [b"nao-json", b"[]", b'{"id":1}', b'{"id":"1","ts":"x","type":"zzz","payload":{}}'])
def test_envelope_invalid(body):
    with pytest.raises(envelope.InvalidEnvelope):
        envelope.decode(body)


def test_topology_has_required_queues_and_dlq():
    assert {"q.influx", "q.inference", "q.websocket", "q.commands", "q.jobs.generate", "q.jobs.train"} <= set(topology.QUEUES)
    assert topology.DLQ_ARGS["x-dead-letter-exchange"] == topology.EX_DLX
    assert topology.telemetry_key("sala-101", "temperature", "temp-101") == "telemetry.sala-101.temperature.temp-101"
    assert "guest" not in topology.SERVICE_PERMISSIONS


def _equipment_df(n=300, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"vibration": rng.normal(1.5, .2, n), "current": rng.normal(7, .3, n),
                         "temperature": rng.normal(62, 1.5, n), "ambient_temp": rng.normal(25, 1, n),
                         "load": rng.uniform(.3, .7, n), "running": np.ones(n)})


def test_features_only_use_past():
    df = _equipment_df()
    f1 = compute_features(df)
    df2 = df.copy()
    df2.loc[200:, "vibration"] = 30.0     # muda o futuro
    f2 = compute_features(df2)
    pd.testing.assert_frame_equal(f1.iloc[:200], f2.iloc[:200])
    assert list(f1.columns) == FEATURE_COLUMNS


def test_features_same_code_grouped_and_single():
    a, b = _equipment_df(seed=1), _equipment_df(seed=2)
    a["equipment"], b["equipment"] = 1, 2
    both = compute_features(pd.concat([a, b], ignore_index=True), group_col="equipment")
    single = compute_features(b.drop(columns="equipment"))
    np.testing.assert_allclose(both.iloc[len(a):].values, single.values, rtol=1e-5)


def test_features_handle_outliers_and_missing():
    df = _equipment_df(50)
    df.loc[10, "vibration"] = -999
    df.loc[11, "temperature"] = np.nan
    f = compute_features(df)
    assert np.isfinite(f.values).all()
    assert f.loc[10, "vibration"] == pytest.approx(df.loc[9, "vibration"], rel=1e-5)


def test_synthetic_reproducible_and_labeled(tmp_path):
    cfg = synthetic.SynthConfig(n_equipment=6, days=10, failure_pct=50, seed=5)
    s1 = synthetic.generate(cfg, str(tmp_path / "a"))
    s2 = synthetic.generate(cfg, str(tmp_path / "b"))
    d1, d2 = synthetic.load_equipment(str(tmp_path / "a")), synthetic.load_equipment(str(tmp_path / "b"))
    np.testing.assert_array_equal(np.nan_to_num(d1["vibration"]), np.nan_to_num(d2["vibration"]))
    assert s1["failing_equipment"] == 3 == s2["failing_equipment"]
    assert d1["rul_h"].max() <= synthetic.RUL_CAP_H and d1["rul_h"].min() >= 0
    assert 0 <= d1["health"].min() and d1["health"].max() <= 100
    assert np.isnan(d1["vibration"]).any()  # leituras faltantes existem


def test_synthetic_degradation_is_progressive(tmp_path):
    cfg = synthetic.SynthConfig(n_equipment=4, days=30, failure_pct=100, missing_pct=0, outlier_pct=0,
                                sensor_fault_pct=0, seed=1)
    synthetic.generate(cfg, str(tmp_path))
    d = synthetic.load_equipment(str(tmp_path))
    for e in np.unique(d["equipment"]):
        m = (d["equipment"] == e) & (d["running"] > 0.5)
        vib, deg = d["vibration"][m], d["degrading"][m]
        early, late = vib[:len(vib) // 3].mean(), vib[-30:].mean()
        assert late > early        # sobe antes da falha
        assert deg[-1] == 1


def test_synthetic_ceiling():
    with pytest.raises(ValueError, match="teto"):
        synthetic.SynthConfig(n_equipment=2000, days=1095, sensors_per_type=20).validate()


def test_split_by_equipment_has_no_leak():
    ids = np.repeat(np.arange(40), 10)
    split = ml.split_by_equipment(ids, seed=1, failing=set(range(0, 40, 2)))
    sets = [set(v.tolist()) for v in split.values()]
    assert not (sets[0] & sets[1]) and not (sets[0] & sets[2]) and not (sets[1] & sets[2])
    assert set().union(*sets) == set(range(40))
    assert any(i % 2 == 0 for i in split["test"]) and any(i % 2 == 1 for i in split["test"])


def test_train_beats_baseline(tmp_path):
    cfg = synthetic.SynthConfig(n_equipment=60, days=45, seed=3)
    synthetic.generate(cfg, str(tmp_path / "ds"))
    res = ml.train(str(tmp_path / "ds"), str(tmp_path / "models"), 1, max_train_rows=150_000)
    for name in ("rul", "health"):
        t = res["targets"][name]
        assert set(t["metrics"]["test"]) == {"mae", "rmse", "r2"}
        assert t["metrics"]["test"]["mae"] < t["baseline"]["test"]["mae"]
        assert t["feature_importance"]
    loaded = ml.load_active(str(tmp_path / "models")) if res["valid"] else None
    if loaded:
        pred = loaded.predict(compute_features(_equipment_df(60)))
        assert 0 <= pred["health"] <= 100 and 0 <= pred["rul"] <= synthetic.RUL_CAP_H


def test_physics_degradation_raises_all_three_signals():
    rng = np.random.default_rng(0)
    prof = {"vib_base": 1.3, "cur_base": 4.2, "temp_base": 55.0}
    ones = np.ones(2000)
    for mode in physics.MECHANICAL_MODES:
        v0, c0, t0 = physics.equipment_readings(ones * 0, mode, ones * 25, ones * .5, ones, prof, 1, rng)
        v1, c1, t1 = physics.equipment_readings(ones * .9, mode, ones * 25, ones * .5, ones, prof, 1, rng)
        assert v1.mean() > v0.mean() and c1.mean() > c0.mean() and t1.mean() > t0.mean()
