from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.time import now_utc
from app.models import CareEvent, RainEvent, Tree
from app.models.enums import CareEventType, EventSource, RainSource, TreeStatus


async def plant(session, code: str, *, days_ago: float = 10, lat=-28.26, lng=-52.40) -> Tree:
    tree = (await session.execute(select(Tree).where(Tree.code == code))).scalar_one()
    tree.status = TreeStatus.PLANTED
    tree.planted_at = now_utc() - timedelta(days=days_ago)
    tree.lat, tree.lng = lat, lng
    await session.commit()
    return tree


async def add_watering(session, tree: Tree, at: datetime, name: str | None = None) -> None:
    session.add(
        CareEvent(
            tree_id=tree.id,
            type=CareEventType.WATERING,
            performed_at=at,
            performed_by_name=name,
            source=EventSource.ADMIN,
        )
    )
    await session.commit()


async def add_rain(session, at: datetime, mm=None) -> None:
    session.add(RainEvent(occurred_at=at, precipitation_mm=mm, source=RainSource.MANUAL))
    await session.commit()
