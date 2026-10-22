"""Admin authentication: JWT bearer tokens + a small login brute-force guard."""
import time
from collections import defaultdict, deque
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.time import now_utc
from app.models import User

_bearer = HTTPBearer(auto_error=False)

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = now_utc()
    payload = {
        "sub": str(user.id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _unauthorized(detail: str = "Sessão expirada. Entre novamente.") -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


async def current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise _unauthorized("Faça login para continuar.")
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        raise _unauthorized() from None
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


class LoginGuard:
    """Failed logins per client (hashed IP). In-memory: fine for a single app process."""

    def __init__(self, max_failures: int = LOGIN_MAX_FAILURES, window: int = LOGIN_WINDOW_SECONDS):
        self.max_failures = max_failures
        self.window = window
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._failures[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int:
        now = time.monotonic()
        q = self._prune(key, now)
        if len(q) < self.max_failures:
            return 0
        return int(self.window - (now - q[0])) + 1

    def fail(self, key: str) -> None:
        self._failures[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


login_guard = LoginGuard()
