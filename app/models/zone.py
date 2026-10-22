from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PlantingZone(TimestampMixin, Base):
    __tablename__ = "planting_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    restrictions: Mapped[str | None] = mapped_column(Text)
    # GeoJSON geometry (Polygon/MultiPolygon). Null until drawn in the admin.
    polygon_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    trees: Mapped[list["Tree"]] = relationship(back_populates="zone")  # noqa: F821
