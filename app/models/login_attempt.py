from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LoginAttempt(Base):
    """Failed admin logins, keyed by hashed IP. In the DB so it works across serverless instances."""

    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_key_created", "key_hash", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
