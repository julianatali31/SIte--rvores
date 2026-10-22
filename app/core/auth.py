"""Admin authentication: JWT bearer tokens + a login brute-force guard stored in the DB."""
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.time import now_utc
from app.models import LoginAttempt, User

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


async def login_retry_after(session: AsyncSession, key: str) -> int:
    """Seconds until this client may try again (0 = allowed)."""
    now = now_utc()
    since = now - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    count, oldest = (
        await session.execute(
            select(func.count(), func.min(LoginAttempt.created_at)).where(
                LoginAttempt.key_hash == key, LoginAttempt.created_at > since
            )
        )
    ).one()
    if count < LOGIN_MAX_FAILURES:
        return 0
    return max(int((oldest + timedelta(seconds=LOGIN_WINDOW_SECONDS) - now).total_seconds()) + 1, 1)


async def record_login_failure(session: AsyncSession, key: str) -> None:
    cutoff = now_utc() - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    await session.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
    session.add(LoginAttempt(key_hash=key))
    await session.commit()


async def clear_login_failures(session: AsyncSession, key: str) -> None:
    await session.execute(delete(LoginAttempt).where(LoginAttempt.key_hash == key))
    await session.commit()
