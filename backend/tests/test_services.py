import json

import pytest

from api.rules import RuleEngine
from ecosala_common.envelope import make_envelope
from gateway.main import command_to_mqtt, split_telemetry
from inference.engine import CLEAR_AFTER, RAISE_AFTER, AlertState, InferenceEngine


def test_gateway_splits_node_message_into_device_messages():
    raw = json.dumps({"ts": "2026-11-20T10:00:00Z", "sensors": {"temp-101": {"type": "temperature", "value": 27.1}},
                      "actuators": {"vent-101": {"type": "vent", "state": True}},
                      "equipment": {"ac-101": {"type": "air_conditioner", "vibration": 1.2, "current": 6,
                                               "temperature": 60, "ambient_temp": 25, "load": .5, "running": True,
                                               "degradation": 0.9}}}).encode()
    out = dict(split_telemetry("ecosala/v1/sala-101/esp32-sala-101/telemetry", raw))
    assert set(out) == {"telemetry.sala-101.temperature.temp-101", "telemetry.sala-101.actuator.vent-101",
                        "telemetry.sala-101.equipment.ac-101"}
    eq = out["telemetry.sala-101.equipment.ac-101"]
    assert eq["device"] == "ac-101" and eq["payload"]["vibration"] == 1.2
    assert "degradation" not in eq["payload"]     # rótulos nunca seguem em tempo real


def test_gateway_status_and_invalid_topic():
    out = split_telemetry("ecosala/v1/sala-101/esp32-sala-101/status", b"offline")
    assert out[0][0] == "status.sala-101.esp32-sala-101" and out[0][1]["payload"]["state"] == "offline"
    with pytest.raises(ValueError):
        split_telemetry("outro/topico", b"{}")


def test_gateway_command_topic():
    env = make_envelope("command", "vent-101", {"action": "on", "node": "esp32-sala-101"}, room="sala-101")
    topic, body = command_to_mqtt(env)
    assert topic == "ecosala/v1/sala-101/esp32-sala-101/command"
    assert body["target"] == "vent-101" and body["action"] == "on"


def _temp(v, dev="temp-101"):
    return make_envelope("telemetry", dev, {"kind": "sensor", "value": v}, room="sala-101")


def test_rule_with_hysteresis():
    eng = RuleEngine()
    eng.load([{"id": 1, "name": "r", "source_device": "temp-101", "operator": ">", "threshold": 28,
               "hysteresis": 1.5, "actuator_device": "vent-101", "enabled": True}])
    assert eng.evaluate(_temp(25)) == []
    assert [a for _, a, _ in eng.evaluate(_temp(28.5))] == ["on"]
    assert eng.evaluate(_temp(29)) == []           # já ligado
    assert eng.evaluate(_temp(27.0)) == []         # dentro da histerese
    assert [a for _, a, _ in eng.evaluate(_temp(26.4))] == ["off"]
    assert eng.evaluate(_temp(30, dev="temp-102")) == []


def test_alert_rule():
    eng = RuleEngine()
    eng.load([{"id": 2, "name": "a", "source_device": "ac-101", "operator": "alert", "threshold": 0,
               "hysteresis": 0, "actuator_device": "alarme-101", "enabled": True}])
    raised = make_envelope("alert", "ac-101", {"state": "raised", "severity": "critico", "kind": "health"})
    cleared = make_envelope("alert", "ac-101", {"state": "cleared", "severity": "info", "kind": "health"})
    assert [a for _, a, _ in eng.evaluate(raised)] == ["on"]
    assert [a for _, a, _ in eng.evaluate(cleared)] == ["off"]


def test_inference_alert_hysteresis():
    st = AlertState()
    events = [InferenceEngine._hysteresis(st, True, "health", "ac", 30, 10, "x") for _ in range(RAISE_AFTER)]
    assert events[-1] and events[-1][0]["state"] == "raised" and not any(events[:-1])
    cleared = [InferenceEngine._hysteresis(st, False, "health", "ac", 90, 100, "x") for _ in range(CLEAR_AFTER)]
    assert cleared[-1][0]["state"] == "cleared" and not any(cleared[:-1])


def test_inference_without_model_is_silent():
    eng = InferenceEngine(None)
    pred, alerts = eng.process("ac-101", {"vibration": 1, "current": 6, "temperature": 60, "ambient_temp": 25,
                                          "load": .5, "running": True})
    assert pred is None and alerts == []


def test_two_rules_same_actuator_do_not_fight():
    eng = RuleEngine()
    eng.load([{"id": 1, "name": "t", "source_device": "temp-101", "operator": ">", "threshold": 28, "hysteresis": 1,
               "actuator_device": "vent-101", "enabled": True},
              {"id": 2, "name": "c", "source_device": "co2-101", "operator": ">", "threshold": 1200, "hysteresis": 200,
               "actuator_device": "vent-101", "enabled": True}])
    assert [a for _, a, _ in eng.evaluate(_temp(29))] == ["on"]
    assert [a for _, a, _ in eng.evaluate(_temp(1300, dev="co2-101"))] == ["on"]
    assert eng.evaluate(_temp(900, dev="co2-101")) == []      # temperatura ainda alta: não desliga
    assert [a for _, a, _ in eng.evaluate(_temp(26))] == ["off"]
