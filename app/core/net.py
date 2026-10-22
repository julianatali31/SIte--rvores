from fastapi import Request

from app.core.config import get_settings


def client_ip(request: Request) -> str | None:
    """Real client IP, used only to compute the hashed rate-limit key.

    On Vercel the edge sets x-real-ip / x-forwarded-for itself (client values are
    overwritten), so they are trustworthy there. Elsewhere uvicorn's
    --proxy-headers + FORWARDED_ALLOW_IPS already resolve request.client.
    """
    if get_settings().vercel:
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
