from simulator.main import Simulator


def _sensor(sim, room, dev):
    for topic, p in sim.tick():
        if p["room"] == room:
            return p, p["sensors"].get(dev)
    raise AssertionError


def test_actuator_changes_next_readings():
    sim = Simulator()
    p, _ = _sensor(sim, "sala-101", "lum-101")
    ok, _ = sim.apply_command("sala-101", {"action": "off", "target": "luz-101"})
    assert ok
    p_off, lum_off = _sensor(sim, "sala-101", "lum-101")
    sim.apply_command("sala-101", {"action": "on", "target": "luz-101"})
    p_on, lum_on = _sensor(sim, "sala-101", "lum-101")
    assert lum_on["value"] > lum_off["value"] + 300
    assert p_on["actuators"]["luz-101"]["state"] is True


def test_fault_injection_and_repair():
    sim = Simulator()
    ok, _ = sim.apply_command("sala-102", {"action": "inject_fault", "target": "ac-102",
                                           "params": {"mode": "rolamento", "hours": 4}})
    assert ok
    for _ in range(40):
        ticks = sim.tick()
    eq = [p for _, p in ticks if p["room"] == "sala-102"][0]["equipment"]["ac-102"]
    assert eq["failed"] is True and eq["running"] is False
    assert "degradation" not in eq and "rul" not in eq
    assert sim.apply_command("sala-102", {"action": "repair", "target": "ac-102"})[0]
    eq = [p for _, p in sim.tick() if p["room"] == "sala-102"][0]["equipment"]["ac-102"]
    assert eq["failed"] is False


def test_invalid_commands_are_rejected():
    sim = Simulator()
    assert not sim.apply_command("sala-999", {"action": "on", "target": "x"})[0]
    assert not sim.apply_command("sala-101", {"action": "on", "target": "nao-existe"})[0]
    assert sim.apply_command("sim", {"action": "pause"})[0] and sim.tick() == []
