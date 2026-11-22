"""Catálogo inicial do campus: salas, sensores, atuadores e equipamentos.

Usado para popular o PostgreSQL na primeira subida (seed) e pelo simulador.
Os mesmos ids são usados no frontend para posicionar cada item na cena 3D.
"""
from __future__ import annotations

ROOMS = ["sala-101", "sala-102", "lab-201"]
EXTERNAL_ROOM = "externo"

# tipo de sensor -> (unidade, faixa normal min, faixa normal max)
SENSOR_TYPES: dict[str, tuple[str, float | None, float | None]] = {
    "temperature": ("°C", 20.0, 26.0),
    "humidity": ("%", 40.0, 65.0),
    "luminosity": ("lux", 300.0, None),
    "co2": ("ppm", None, 1000.0),
    "presence": ("pessoas", None, 40.0),
}

ACTUATOR_TYPES = {
    "fan": "Ventilação/exaustor",
    "light": "Iluminação",
    "alarm": "Sinalização (alarme)",
}


def _num(room: str) -> str:
    return room.split("-")[-1]


def node_id(room: str) -> str:
    return f"esp32-{room}"


def default_devices() -> list[dict]:
    devices: list[dict] = []
    names = {"temperature": "Temperatura", "humidity": "Umidade", "luminosity": "Luminosidade",
             "co2": "CO₂ (qualidade do ar)", "presence": "Presença (ocupação)"}
    prefixes = {"temperature": "temp", "humidity": "umid", "luminosity": "lum", "co2": "co2",
                "presence": "pres"}
    for room in ROOMS:
        n = _num(room)
        for stype, (unit, lo, hi) in SENSOR_TYPES.items():
            devices.append({
                "id": f"{prefixes[stype]}-{n}", "name": f"{names[stype]} {room}", "room": room,
                "kind": "sensor", "type": stype, "unit": unit, "normal_min": lo, "normal_max": hi,
                "controllable": False, "node": node_id(room),
            })
        devices += [
            {"id": f"vent-{n}", "name": f"Ventilação {room}", "room": room, "kind": "actuator",
             "type": "fan", "unit": None, "normal_min": None, "normal_max": None,
             "controllable": True, "node": node_id(room)},
            {"id": f"luz-{n}", "name": f"Iluminação {room}", "room": room, "kind": "actuator",
             "type": "light", "unit": None, "normal_min": None, "normal_max": None,
             "controllable": True, "node": node_id(room)},
            {"id": f"alarme-{n}", "name": f"Sinalização {room}", "room": room, "kind": "actuator",
             "type": "alarm", "unit": None, "normal_min": None, "normal_max": None,
             "controllable": True, "node": node_id(room)},
            {"id": f"ac-{n}", "name": f"Ar-condicionado {room}", "room": room, "kind": "equipment",
             "type": "air_conditioner", "unit": None, "normal_min": None, "normal_max": None,
             "controllable": True, "node": node_id(room)},
        ]
    devices += [
        {"id": "temp-ext", "name": "Temperatura externa", "room": EXTERNAL_ROOM, "kind": "sensor",
         "type": "temperature", "unit": "°C", "normal_min": None, "normal_max": None,
         "controllable": False, "node": node_id(EXTERNAL_ROOM)},
        {"id": "lum-ext", "name": "Luminosidade externa (dia/noite)", "room": EXTERNAL_ROOM,
         "kind": "sensor", "type": "luminosity", "unit": "lux", "normal_min": None,
         "normal_max": None, "controllable": False, "node": node_id(EXTERNAL_ROOM)},
    ]
    return devices


def default_rules() -> list[dict]:
    rules = []
    for room in ROOMS:
        n = _num(room)
        rules.append({"name": f"Temperatura alta liga ventilação ({room})", "source_device": f"temp-{n}",
                      "operator": ">", "threshold": 28.0, "hysteresis": 1.5,
                      "actuator_device": f"vent-{n}", "enabled": True})
        rules.append({"name": f"CO₂ alto liga ventilação ({room})", "source_device": f"co2-{n}",
                      "operator": ">", "threshold": 1200.0, "hysteresis": 200.0,
                      "actuator_device": f"vent-{n}", "enabled": True})
        rules.append({"name": f"Alerta crítico da IA aciona sinalização ({room})",
                      "source_device": f"ac-{n}", "operator": "alert", "threshold": 0.0,
                      "hysteresis": 0.0, "actuator_device": f"alarme-{n}", "enabled": True})
    return rules
