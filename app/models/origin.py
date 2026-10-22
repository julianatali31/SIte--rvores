from datetime import date

from sqlalchemy import CheckConstraint, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Origin(TimestampMixin, Base):
    __tablename__ = "origins"
    __table_args__ = (CheckConstraint("seedling_count >= 0", name="seedling_count_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_name: Mapped[str] = mapped_column(String(160), unique=True)
    donated_at: Mapped[date | None] = mapped_column(Date)
    seedling_count: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)

    trees: Mapped[list["Tree"]] = relationship(back_populates="origin")  # noqa: F821
