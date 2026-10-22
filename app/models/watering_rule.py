from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import WateringPhase


class WateringRule(TimestampMixin, Base):
    """Watering interval per tree phase.

    Seeded values are PLACEHOLDERS (is_placeholder=True) until confirmed by
    NUGAI/engineering. Do not treat them as agronomic guidance.
    """

    __tablename__ = "watering_rules"
    __table_args__ = (
        CheckConstraint("interval_days > 0", name="interval_positive"),
        CheckConstraint("phase_until_days IS NULL OR phase_until_days > 0", name="until_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    phase: Mapped[WateringPhase] = mapped_column(
        str_enum(WateringPhase, "watering_phase"), unique=True
    )
    interval_days: Mapped[float]
    # Days since planting while this phase applies (null = open-ended).
    phase_until_days: Mapped[int | None]
    is_placeholder: Mapped[bool] = mapped_column(default=True)
    note: Mapped[str | None] = mapped_column(String(280))
