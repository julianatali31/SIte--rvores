from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Double, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import TreeStatus


class Tree(TimestampMixin, Base):
    __tablename__ = "trees"
    __table_args__ = (
        CheckConstraint(
            "status NOT IN ('planted', 'attention') OR planted_at IS NOT NULL",
            name="planted_requires_date",
        ),
        CheckConstraint("lat IS NULL OR lat BETWEEN -90 AND 90", name="lat_range"),
        CheckConstraint("lng IS NULL OR lng BETWEEN -180 AND 180", name="lng_range"),
        CheckConstraint("(lat IS NULL) = (lng IS NULL)", name="lat_lng_together"),
        CheckConstraint("planting_batch IS NULL OR planting_batch > 0", name="batch_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    # Random, non-sequential; this is what goes on the QR code.
    public_id: Mapped[str] = mapped_column(String(8), unique=True)
    species_id: Mapped[int] = mapped_column(ForeignKey("species.id", ondelete="RESTRICT"), index=True)
    origin_id: Mapped[int] = mapped_column(ForeignKey("origins.id", ondelete="RESTRICT"), index=True)
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("planting_zones.id", ondelete="SET NULL"), index=True
    )
    planting_batch: Mapped[int | None]
    status: Mapped[TreeStatus] = mapped_column(
        str_enum(TreeStatus, "tree_status"), default=TreeStatus.AWAITING_PLANTING, index=True
    )
    planted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lat: Mapped[float | None] = mapped_column(Double)
    lng: Mapped[float | None] = mapped_column(Double)
    notes: Mapped[str | None] = mapped_column(Text)

    species: Mapped["Species"] = relationship(back_populates="trees")  # noqa: F821
    origin: Mapped["Origin"] = relationship(back_populates="trees")  # noqa: F821
    zone: Mapped["PlantingZone | None"] = relationship(back_populates="trees")  # noqa: F821
    care_events: Mapped[list["CareEvent"]] = relationship(  # noqa: F821
        back_populates="tree", cascade="all, delete-orphan", passive_deletes=True
    )
    photos: Mapped[list["Photo"]] = relationship(  # noqa: F821
        back_populates="tree", cascade="all, delete-orphan", passive_deletes=True
    )
