from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import DataReviewStatus


class Species(TimestampMixin, Base):
    __tablename__ = "species"

    id: Mapped[int] = mapped_column(primary_key=True)
    common_name: Mapped[str] = mapped_column(String(120), unique=True)
    scientific_name: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    size_class: Mapped[str | None] = mapped_column(String(60))
    root_notes: Mapped[str | None] = mapped_column(Text)
    fruiting_season: Mapped[str | None] = mapped_column(String(120))
    fun_fact: Mapped[str | None] = mapped_column(Text)
    photo_path: Mapped[str | None] = mapped_column(String(255))
    data_review_status: Mapped[DataReviewStatus] = mapped_column(
        str_enum(DataReviewStatus, "data_review_status"), default=DataReviewStatus.PENDING
    )

    trees: Mapped[list["Tree"]] = relationship(back_populates="species")  # noqa: F821
