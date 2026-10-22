"""Abuse protection for the public watering endpoint.

Counts are taken from care_events (persisted, works with several workers).
Only an HMAC of the IP is stored; the raw IP never touches the database.
"""
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import CareEvent
from app.models.enums import EventSource


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    salt = get_settings().ip_hash_salt.encode()
    return hmac.new(salt, ip.encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0


async def check_ip_rate_limit(session: AsyncSession, ip_hash: str | None, now: datetime) -> RateLimitResult:
    settings = get_settings()
    if ip_hash is None:
        return RateLimitResult(allowed=True)
    window = timedelta(minutes=settings.watering_rate_limit_window_minutes)
    since = now - window
    count, oldest = (
        await session.execute(
            select(func.count(), func.min(CareEvent.created_at)).where(
                CareEvent.ip_hash == ip_hash,
                CareEvent.source == EventSource.PUBLIC,
                CareEvent.created_at > since,
            )
        )
    ).one()
    if count < settings.watering_rate_limit_count:
        return RateLimitResult(allowed=True)
    retry = int((oldest + window - now).total_seconds()) + 1
    return RateLimitResult(allowed=False, retry_after_seconds=max(retry, 1))
