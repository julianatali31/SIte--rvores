from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, str_enum
from app.models.enums import CareEventType, EventSource


class CareEvent(Base):
    __tablename__ = "care_events"
    __table_args__ = (
        # Serves "last watering" (MAX(performed_at)) — computed by query, never by trigger.
        Index("ix_care_events_tree_type_performed", "tree_id", "type", "performed_at"),
        Index("ix_care_events_ip_hash_created", "ip_hash", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tree_id: Mapped[int] = mapped_column(ForeignKey("trees.id", ondelete="CASCADE"))
    type: Mapped[CareEventType] = mapped_column(str_enum(CareEventType, "care_event_type"))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    performed_by_name: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(String(280))
    source: Mapped[EventSource] = mapped_column(str_enum(EventSource, "event_source"))
    # HMAC-SHA256(ip, IP_HASH_SALT). The raw IP is never stored.
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tree: Mapped["Tree"] = relationship(back_populates="care_events")  # noqa: F821
