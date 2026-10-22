from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, current_admin, login_guard
from app.core.db import get_session
from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.admin import LoginIn, TokenOut
from app.services.rate_limit import hash_ip

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Verified against when the username does not exist, so timing does not reveal valid usernames.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, session: AsyncSession = Depends(get_session)):
    key = hash_ip(request.client.host if request.client else None) or "unknown"
    wait = login_guard.retry_after(key)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Muitas tentativas. Aguarde alguns minutos.",
            headers={"Retry-After": str(wait)},
        )
    user = (await session.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    ok = verify_password(user.password_hash if user else _DUMMY_HASH, body.password)
    if not (user and ok and user.is_active):
        login_guard.fail(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário ou senha incorretos.")
    login_guard.reset(key)
    return TokenOut(access_token=create_access_token(user), username=user.username)


@router.get("/me")
async def me(user: User = Depends(current_admin)) -> dict[str, str]:
    return {"username": user.username}
