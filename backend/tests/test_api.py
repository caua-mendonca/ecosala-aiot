"""Testes da API com banco e broker substituídos por dublês em memória."""
import time

import pytest
from fastapi.testclient import TestClient

from api import db, security
from api.bus import bus


class FakeDB:
    def __init__(self):
        self.users = {"operador": {"id": 1, "username": "operador", "role": "operator", "failed_attempts": 0,
                                   "password_hash": "ok:segredo", "locked": False, "lock_left": 0}}
        self.audits = []
        self.devices = {"vent-101": {"id": "vent-101", "room": "sala-101", "node": "esp32-sala-101",
                                     "controllable": True, "enabled": True, "kind": "actuator"},
                        "temp-101": {"id": "temp-101", "room": "sala-101", "node": "esp32-sala-101",
                                     "controllable": False, "enabled": True, "kind": "sensor"}}

    def one(self, sql, params=None):
        if "FROM users" in sql:
            return self.users.get(params[0])
        if "FROM devices" in sql:
            return self.devices.get(params[0])
        return None

    def query(self, sql, params=None):
        return []

    def execute(self, sql, params=None):
        if "failed_attempts=%s" in sql:
            for u in self.users.values():
                u["failed_attempts"] = params[0]
        if "locked_until=now()" in sql:
            for u in self.users.values():
                u["locked"] = True


@pytest.fixture
def client(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(db, "one", fake.one)
    monkeypatch.setattr(db, "query", fake.query)
    monkeypatch.setattr(db, "execute", fake.execute)
    monkeypatch.setattr(db, "audit", lambda *a, **k: fake.audits.append(a))
    monkeypatch.setattr(db, "check_password", lambda pw, h: h == f"ok:{pw}")
    sent = []

    async def send_command(device, action, params, issued_by):
        sent.append((device["id"], action, issued_by))
        return {"id": "cmd1"}
    monkeypatch.setattr(bus, "send_command", send_command)
    security.login_ip_limiter.events.clear()
    from api.main import app
    app.router.lifespan_context = _no_lifespan
    with TestClient(app) as c:
        c.fake, c.sent = fake, sent
        yield c


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _no_lifespan(app):
    yield


def _login(c, user="operador", pw="segredo"):
    return c.post("/api/v1/auth/login", json={"username": user, "password": pw})


def test_login_and_me(client):
    r = _login(client)
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.json()["role"] == "operator"
    assert any(a[1] == "login.sucesso" for a in client.fake.audits)


def test_login_wrong_password_and_lock(client):
    for _ in range(5):
        assert _login(client, pw="errada").status_code == 401
    assert _login(client).status_code == 429


def test_requires_auth_and_role(client):
    assert client.get("/api/v1/devices").status_code == 401
    tok = _login(client).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.post("/api/v1/lab/generate", json={}, headers=h).status_code == 403   # operador não gera dados
    assert client.get("/api/v1/audit", headers=h).status_code == 403


def test_command_goes_to_bus_and_audit(client):
    h = {"Authorization": f"Bearer {_login(client).json()['access_token']}"}
    r = client.post("/api/v1/devices/vent-101/command", json={"action": "on"}, headers=h)
    assert r.status_code == 200, r.text
    assert client.sent == [("vent-101", "on", "operador")]
    assert any(a[1] == "comando.on" for a in client.fake.audits)
    assert client.post("/api/v1/devices/temp-101/command", json={"action": "on"}, headers=h).status_code == 400


def test_ws_ticket_single_use(client):
    h = {"Authorization": f"Bearer {_login(client).json()['access_token']}"}
    t = client.post("/api/v1/auth/ws-ticket", headers=h).json()["ticket"]
    with client.websocket_connect(f"/ws?ticket={t}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["user"] == "operador"
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws?ticket={t}") as ws:
            ws.receive_json()


def test_lab_estimate(client):
    h = {"Authorization": f"Bearer {_login(client).json()['access_token']}"}
    r = client.post("/api/v1/lab/estimate", json={"n_equipment": 100, "days": 90}, headers=h).json()
    assert r["ok"] and r["total_readings"] > 1_000_000


def test_openapi_docs(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/assistant/chat" in paths and "/api/v1/messaging/overview" in paths


def test_limiter():
    lim = security.SlidingWindowLimiter(2, 60)
    assert lim.hit("a") and lim.hit("a") and not lim.hit("a") and lim.hit("b")


def test_jwt_roundtrip_and_tamper():
    tok = security.create_token("x", "admin")
    assert security.decode_token(tok).role == "admin"
    with pytest.raises(Exception):
        security.decode_token(tok[:-2] + "aa")
