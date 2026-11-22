"""Simulador de dispositivos IoT do EcoSala (substitui o ESP32 no 2º bimestre).

- publica telemetria de cada sala no Mosquitto (MQTT, QoS 1);
- escuta comandos e muda o estado dos atuadores (o efeito aparece nas
  leituras seguintes: ventilação reduz temperatura e CO₂, iluminação aumenta a
  luminosidade, ar-condicionado liga o compressor);
- simula o desgaste dos ar-condicionados com o MESMO modelo físico do gerador
  sintético (ecosala_common.physics);
- os rótulos de verdade (degradação, vida útil real) NUNCA são publicados.

Tempo simulado: cada tick (TICK_SECONDS reais) avança SAMPLE_MINUTES minutos.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np
import paho.mqtt.client as mqtt

from ecosala_common import catalog, physics
from ecosala_common.health import beat
from ecosala_common.config import SAMPLE_MINUTES, env, env_float, env_int

log = logging.getLogger("simulador")
PREFIX = "ecosala/v1"
SIM_NODE = "simulator"
SIM_ROOM = "sim"


@dataclass
class Equipment:
    id: str
    profile: dict
    rng: np.random.Generator
    mode: str | None = None
    progress: float = 0.0            # 0..1 até a falha
    step: float = 0.0                # progresso por tick
    failed: bool = False

    @property
    def degradation(self) -> float:
        return self.progress ** 1.4


@dataclass
class Room:
    id: str
    n: str
    temperature: float = 24.0
    humidity: float = 55.0
    co2: float = 450.0
    presence: float = 0.0
    actuators: dict[str, bool] = field(default_factory=dict)
    equipment: Equipment | None = None


class Simulator:
    def __init__(self) -> None:
        self.seed = env_int("SIM_SEED", 2026)
        self.rng = np.random.default_rng(self.seed)
        self.tick_seconds = env_float("TICK_SECONDS", 2.0)
        self.noise = env_float("SIM_NOISE", 1.0)
        self.paused = False
        self.lock = threading.Lock()
        self.sim_time = datetime.now(UTC).replace(hour=7, minute=0, second=0, microsecond=0)
        self.ext_temp = 24.0
        self.ext_lux = 0.0
        self.rooms: dict[str, Room] = {}
        for room in catalog.ROOMS:
            n = room.split("-")[-1]
            erng = np.random.default_rng([self.seed, int(n)])
            r = Room(id=room, n=n, actuators={f"vent-{n}": False, f"luz-{n}": True,
                                              f"alarme-{n}": False, f"ac-{n}": True})
            r.equipment = Equipment(id=f"ac-{n}", profile=physics.machine_profile(erng), rng=erng)
            self.rooms[room] = r
        # desgaste natural lento em uma das máquinas, para a demonstração
        natural = os.getenv("SIM_NATURAL_FAULT", "lab-201:rolamento:9")
        if natural:
            room, mode, days = natural.split(":")
            if room in self.rooms and self.rooms[room].equipment:
                self._start_fault(self.rooms[room].equipment, mode, float(days) * 24, start=0.15)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"simulador-{os.getpid()}", clean_session=True)
        self.client.username_pw_set(env("MQTT_DEVICE_USER", "device"), env("MQTT_DEVICE_PASSWORD"))
        self.client.will_set(f"{PREFIX}/{SIM_ROOM}/{SIM_NODE}/status", "offline", qos=1, retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(1, 10)

    # ------------------------------------------------------------------ MQTT
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):  # noqa: ANN001
        log.info("conectado ao Mosquitto (%s)", reason_code)
        client.subscribe(f"{PREFIX}/+/+/command", qos=1)
        client.publish(f"{PREFIX}/{SIM_ROOM}/{SIM_NODE}/status", "online", qos=1, retain=True)
        for room in list(self.rooms) + [catalog.EXTERNAL_ROOM]:
            client.publish(f"{PREFIX}/{room}/{catalog.node_id(room)}/status", "online", qos=1, retain=True)

    def _on_message(self, client, userdata, msg):  # noqa: ANN001
        try:
            cmd = json.loads(msg.payload)
            parts = msg.topic.split("/")
            room = parts[2]
            ok, detail = self.apply_command(room, cmd)
        except Exception as exc:  # comando inválido não derruba o simulador
            log.warning("comando inválido em %s: %s", msg.topic, exc)
            return
        ack = {"command_id": cmd.get("id"), "target": cmd.get("target"), "action": cmd.get("action"),
               "ok": ok, "detail": detail, "ts": datetime.now(UTC).isoformat()}
        client.publish(msg.topic.rsplit("/", 1)[0] + "/ack", json.dumps(ack), qos=1)
        log.info("comando %s -> %s: %s", cmd.get("action"), cmd.get("target"), detail)

    # --------------------------------------------------------------- comandos
    def apply_command(self, room_id: str, cmd: dict) -> tuple[bool, str]:
        action = str(cmd.get("action", ""))
        target = str(cmd.get("target", ""))
        params = cmd.get("params") or {}
        with self.lock:
            if room_id == SIM_ROOM:
                if action == "pause":
                    self.paused = True
                    return True, "simulador pausado"
                if action == "resume":
                    self.paused = False
                    return True, "simulador retomado"
                return False, f"ação desconhecida: {action}"
            room = self.rooms.get(room_id)
            if room is None:
                return False, f"sala desconhecida: {room_id}"
            if action in {"on", "off"}:
                if target not in room.actuators:
                    return False, f"atuador desconhecido: {target}"
                room.actuators[target] = action == "on"
                return True, f"{target} {'ligado' if action == 'on' else 'desligado'}"
            eq = room.equipment
            if eq is None or target != eq.id:
                return False, f"equipamento desconhecido: {target}"
            if action == "inject_fault":
                mode = str(params.get("mode", "rolamento"))
                if mode not in physics.MECHANICAL_MODES:
                    return False, f"modo inválido: {mode}"
                hours = float(params.get("hours", 48))
                self._start_fault(eq, mode, max(hours, 2.0), start=float(params.get("start", 0.35)))
                return True, f"falha '{mode}' injetada em {eq.id}"
            if action == "repair":
                eq.mode, eq.progress, eq.step, eq.failed = None, 0.0, 0.0, False
                room.actuators[eq.id] = True
                return True, f"{eq.id} reparado"
            return False, f"ação desconhecida: {action}"

    def _start_fault(self, eq: Equipment, mode: str, hours: float, start: float) -> None:
        ticks = hours * 60.0 / SAMPLE_MINUTES
        eq.mode, eq.progress, eq.step, eq.failed = mode, max(eq.progress, start), 1.0 / ticks, False

    # ------------------------------------------------------------------ física
    def _step_environment(self) -> None:
        t = self.sim_time
        hour = t.hour + t.minute / 60.0
        doy = t.timetuple().tm_yday
        weekday = t.weekday() < 5
        season = 4.5 * math.sin(2 * math.pi * (doy - 20) / 365.0)
        self.ext_temp = 24.0 + season + 5.0 * math.sin(2 * math.pi * (hour - 9.0) / 24.0) + random.gauss(0, 0.3)
        self.ext_lux = max(0.0, math.sin(math.pi * (hour - 6.0) / 12.0)) * 60000.0 * 0.85
        in_class = weekday and (7.5 <= hour < 12 or 13.5 <= hour < 17.5 or 19 <= hour < 22.5)
        for room in self.rooms.values():
            target_p = 26 if in_class else 0
            room.presence = float(max(0, round(room.presence + 0.5 * (target_p - room.presence)
                                               + random.gauss(0, 2 if in_class else 0.3))))
            eq = room.equipment
            ac_running = bool(room.actuators.get(f"ac-{room.n}")) and eq is not None and not eq.failed
            fan = room.actuators.get(f"vent-{room.n}", False)
            target = 0.55 * self.ext_temp + 11.0 + 0.12 * room.presence
            room.temperature += 0.25 * (target - room.temperature) - (0.9 if ac_running else 0.0) \
                - (0.45 if fan else 0.0) + random.gauss(0, 0.12 * self.noise)
            room.co2 += 0.25 * (420 + 32 * room.presence - room.co2) - (0.35 * (room.co2 - 420) if fan else 0.0) \
                + random.gauss(0, 12 * self.noise)
            room.humidity += 0.2 * ((60.0 - 0.8 * (self.ext_temp - 24) + 0.15 * room.presence
                                     - (6 if ac_running else 0)) - room.humidity) + random.gauss(0, 0.6)

    def _equipment_payload(self, room: Room) -> dict:
        eq = room.equipment
        assert eq is not None
        if eq.mode and not eq.failed:
            eq.progress = min(1.0, eq.progress + eq.step)
            if eq.progress >= 1.0:
                eq.failed = True
                log.warning("%s FALHOU (%s)", eq.id, eq.mode)
        running = 1.0 if (room.actuators.get(eq.id) and not eq.failed) else 0.0
        load = float(np.clip(running * (0.40 + 0.025 * (self.ext_temp - 20.0) + 0.006 * room.presence
                                        + eq.rng.normal(0, 0.05)), 0.0, 1.0))
        vib, cur, tmp = physics.equipment_readings(
            np.array([eq.degradation]), eq.mode, np.array([self.ext_temp]), np.array([load]),
            np.array([running]), eq.profile, self.noise, eq.rng)
        return {"type": "air_conditioner", "enabled": bool(room.actuators.get(eq.id)),
                "running": bool(running), "failed": eq.failed,
                "vibration": round(float(vib[0]), 3), "current": round(float(cur[0]), 3),
                "temperature": round(float(tmp[0]), 2), "ambient_temp": round(self.ext_temp, 2),
                "load": round(load, 3)}

    def tick(self) -> list[tuple[str, dict]]:
        with self.lock:
            if self.paused:
                return []
            self.sim_time += timedelta(minutes=SAMPLE_MINUTES)
            self._step_environment()
            now = datetime.now(UTC).isoformat(timespec="milliseconds")
            sim = self.sim_time.isoformat(timespec="minutes")
            out = []
            for room in self.rooms.values():
                n = room.n
                lux = self.ext_lux * 0.01 + (450.0 if room.actuators.get(f"luz-{n}") else 0.0) + random.gauss(0, 15)
                sensors = {
                    f"temp-{n}": {"type": "temperature", "value": round(room.temperature, 2)},
                    f"umid-{n}": {"type": "humidity", "value": round(min(100, max(0, room.humidity)), 1)},
                    f"lum-{n}": {"type": "luminosity", "value": round(max(0.0, lux), 0)},
                    f"co2-{n}": {"type": "co2", "value": round(max(380.0, room.co2), 0)},
                    f"pres-{n}": {"type": "presence", "value": room.presence},
                }
                kinds = {"vent": "fan", "luz": "light", "alarme": "alarm"}
                actuators = {k: {"type": kinds.get(k.split("-")[0], "actuator"), "state": v}
                             for k, v in room.actuators.items() if not k.startswith("ac-")}
                payload = {"node": catalog.node_id(room.id), "room": room.id, "ts": now, "sim_time": sim,
                           "sensors": sensors, "actuators": actuators,
                           "equipment": {room.equipment.id: self._equipment_payload(room)} if room.equipment else {}}
                out.append((f"{PREFIX}/{room.id}/{catalog.node_id(room.id)}/telemetry", payload))
            ext = {"node": catalog.node_id(catalog.EXTERNAL_ROOM), "room": catalog.EXTERNAL_ROOM, "ts": now,
                   "sim_time": sim, "sensors": {
                       "temp-ext": {"type": "temperature", "value": round(self.ext_temp, 2)},
                       "lum-ext": {"type": "luminosity", "value": round(self.ext_lux, 0)}},
                   "actuators": {}, "equipment": {}}
            out.append((f"{PREFIX}/{catalog.EXTERNAL_ROOM}/{catalog.node_id(catalog.EXTERNAL_ROOM)}/telemetry", ext))
            return out

    def run(self) -> None:
        host = os.getenv("MQTT_HOST", "mosquitto")
        port = env_int("MQTT_PORT", 1883)
        while True:
            try:
                self.client.connect(host, port, keepalive=30)
                break
            except OSError as exc:
                log.warning("Mosquitto indisponível (%s); tentando de novo", exc)
                time.sleep(2)
        self.client.loop_start()
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        log.info("simulando %d salas, tick=%.1fs, %d min simulados por tick",
                 len(self.rooms), self.tick_seconds, SAMPLE_MINUTES)
        while not stop.is_set():
            started = time.time()
            beat()
            for topic, payload in self.tick():
                self.client.publish(topic, json.dumps(payload), qos=1)
            stop.wait(max(0.0, self.tick_seconds - (time.time() - started)))
        self.client.publish(f"{PREFIX}/{SIM_ROOM}/{SIM_NODE}/status", "offline", qos=1, retain=True)
        for room in list(self.rooms) + [catalog.EXTERNAL_ROOM]:
            self.client.publish(f"{PREFIX}/{room}/{catalog.node_id(room)}/status", "offline", qos=1, retain=True)
        time.sleep(0.5)
        self.client.loop_stop()
        self.client.disconnect()


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    Simulator().run()


if __name__ == "__main__":
    main()
