from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from .. import db, settings
from ..security import (ROLE_LABEL, User, create_token, current_user, login_ip_limiter, require, tickets)

router = APIRouter(prefix="/auth", tags=["autenticação"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login", summary="Login com usuário e senha (devolve JWT)")
def login(body: LoginIn, request: Request) -> dict:
    ip = request.client.host if request.client else "?"
    if not login_ip_limiter.hit(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "muitas tentativas; aguarde um minuto")
    user = db.one("""SELECT *, (locked_until IS NOT NULL AND locked_until > now()) AS locked,
                     GREATEST(0, EXTRACT(EPOCH FROM (locked_until - now())))::int AS lock_left
                     FROM users WHERE username=%s""", (body.username,))
    if user and user["locked"]:
        db.audit(body.username, "login.bloqueado", None, {"ip": ip})
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"usuário bloqueado por excesso de tentativas; tente em {user['lock_left']} s")
    if not user or not db.check_password(body.password, user["password_hash"]):
        if user:
            attempts = user["failed_attempts"] + 1
            if attempts >= settings.LOGIN_MAX_ATTEMPTS:
                db.execute("UPDATE users SET failed_attempts=0, locked_until=now() + make_interval(mins => %s) "
                           "WHERE id=%s", (settings.LOGIN_LOCK_MINUTES, user["id"]))
            else:
                db.execute("UPDATE users SET failed_attempts=%s WHERE id=%s", (attempts, user["id"]))
        db.audit(body.username, "login.falha", None, {"ip": ip})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuário ou senha inválidos")
    db.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=%s", (user["id"],))
    db.audit(user["username"], "login.sucesso", None, {"ip": ip, "papel": user["role"]})
    return {"access_token": create_token(user["username"], user["role"]), "token_type": "bearer",
            "username": user["username"], "role": user["role"], "role_label": ROLE_LABEL[user["role"]]}


@router.get("/me", summary="Usuário logado")
def me(user: User = Depends(current_user)) -> dict:
    return {"username": user.username, "role": user.role, "role_label": ROLE_LABEL[user.role]}


@router.post("/ws-ticket", summary="Ticket curto e de uso único para abrir o WebSocket")
def ws_ticket(user: User = Depends(current_user)) -> dict:
    return {"ticket": tickets.issue(user), "expires_in": int(tickets.TTL)}


@router.get("/users", summary="Lista usuários (administrador)")
def users(_: User = Depends(require("admin"))) -> list[dict]:
    return db.query("SELECT id, username, role, created_at, locked_until FROM users ORDER BY id")
