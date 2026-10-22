"""Store in UTC, display in America/Sao_Paulo."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime: all datetimes must be timezone-aware")
    return dt.astimezone(local_tz())


def assume_local(dt: datetime) -> datetime:
    """Naive datetimes typed in the admin are São Paulo local time."""
    return dt.replace(tzinfo=local_tz()) if dt.tzinfo is None else dt
