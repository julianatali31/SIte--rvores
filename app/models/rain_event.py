from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, str_enum
from app.models.enums import RainSource


class RainEvent(Base):
    """Campus-wide rain. Counts as 'last water received' for every planted tree."""

    __tablename__ = "rain_events"
    __table_args__ = (
        CheckConstraint(
            "precipitation_mm IS NULL OR precipitation_mm >= 0", name="precipitation_non_negative"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    precipitation_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    source: Mapped[RainSource] = mapped_column(str_enum(RainSource, "rain_source"))
    notes: Mapped[str | None] = mapped_column(String(280))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
