"""Autenticação JWT, papéis, limite de tentativas e tickets de WebSocket."""
from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import settings

ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3}
ROLE_LABEL = {"viewer": "visualizador", "operator": "operador", "admin": "administrador"}
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class User:
    username: str
    role: str


def create_token(username: str, role: str) -> str:
    now = datetime.now(UTC)
    payload = {"sub": username, "role": role, "iat": now,
               "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES), "iss": "ecosala"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> User:
    try:
        data = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"], issuer="ecosala")
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido ou expirado") from exc
    if data.get("role") not in ROLE_LEVEL:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "papel inválido")
    return User(username=data["sub"], role=data["role"])


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "faça login", headers={"WWW-Authenticate": "Bearer"})
    return decode_token(cred.credentials)


def require(role: str):  # noqa: ANN201
    def dep(user: User = Depends(current_user)) -> User:
        if ROLE_LEVEL[user.role] < ROLE_LEVEL[role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requer papel {ROLE_LABEL[role]}")
        return user
    return dep


class SlidingWindowLimiter:
    """Limite simples em memória: no máximo `limit` eventos por `window` segundos por chave."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit, self.window = limit, window
        self.events: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def hit(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.events[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True

    def retry_after(self, key: str) -> int:
        q = self.events.get(key)
        if not q:
            return 0
        return max(1, int(self.window - (time.monotonic() - q[0])) + 1)


login_ip_limiter = SlidingWindowLimiter(limit=20, window=60)
assistant_limiter = SlidingWindowLimiter(limit=settings.ASSISTANT_PER_MINUTE, window=60)


class TicketStore:
    """Tickets curtos e de uso único para abrir o WebSocket (o JWT nunca vai na URL)."""

    TTL = 30.0

    def __init__(self) -> None:
        self._tickets: dict[str, tuple[User, float]] = {}
        self._lock = threading.Lock()

    def issue(self, user: User) -> str:
        ticket = secrets.token_urlsafe(24)
        with self._lock:
            now = time.monotonic()
            self._tickets = {k: v for k, v in self._tickets.items() if v[1] > now}
            self._tickets[ticket] = (user, now + self.TTL)
        return ticket

    def consume(self, ticket: str) -> User | None:
        with self._lock:
            item = self._tickets.pop(ticket, None)
        if item is None or item[1] < time.monotonic():
            return None
        return item[0]


tickets = TicketStore()
