"""Builds the public tree payload. 'Last watering' comes from queries, never triggers."""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.time import local_tz
from app.models import CareEvent, Photo, RainEvent, Tree, WateringRule
from app.models.enums import TREE_STATUS_LABELS, CareEventType, TreeStatus
from app.schemas.public import (
    BadgeOut,
    LocationOut,
    OriginOut,
    PhotoOut,
    SpeciesOut,
    TreeOut,
    WateringOut,
)
from app.services import humanize
from app.services.watering import BadgeColor, RuleSpec, compute_badge, due_at, last_water, select_rule

WATERABLE = {TreeStatus.PLANTED, TreeStatus.ATTENTION}
RECENT_RAIN_HOURS = 24

HINTS = {
    BadgeColor.GREEN: "Está em dia. Não precisa regar agora.",
    BadgeColor.YELLOW: "Logo vai precisar de água.",
    BadgeColor.RED: "Precisa de água! Se puder, regue.",
    BadgeColor.GREY: "Ainda não há registro de rega. Se regar, registre aqui.",
}


def _due_text(color: BadgeColor, due: datetime | None, tz) -> str | None:
    if due is None:
        return None
    label = humanize.date_label(due, tz)
    return f"Rega atrasada desde {label}" if color == BadgeColor.RED else f"Próxima rega até {label}"


def media_url(path: str | None) -> str | None:
    return f"/media/{path}" if path else None


async def load_tree(session: AsyncSession, public_id: str, *, for_update: bool = False) -> Tree | None:
    stmt = select(Tree).where(Tree.public_id == public_id)
    if for_update:
        # Serializes concurrent waterings of the same tree (min-interval check).
        stmt = stmt.with_for_update()
    stmt = stmt.options(selectinload(Tree.species), selectinload(Tree.origin), selectinload(Tree.zone))
    return (await session.execute(stmt)).scalar_one_or_none()


async def last_watering_at(session: AsyncSession, tree_id: int) -> datetime | None:
    return await session.scalar(
        select(func.max(CareEvent.performed_at)).where(
            CareEvent.tree_id == tree_id, CareEvent.type == CareEventType.WATERING
        )
    )


async def last_rain_at(session: AsyncSession, now: datetime) -> datetime | None:
    return await session.scalar(select(func.max(RainEvent.occurred_at)).where(RainEvent.occurred_at <= now))


async def _rules(session: AsyncSession) -> tuple[list[RuleSpec], dict]:
    rows = (await session.execute(select(WateringRule))).scalars().all()
    specs = [RuleSpec(r.phase, r.interval_days, r.phase_until_days) for r in rows]
    return specs, {r.phase: r.is_placeholder for r in rows}


def _make_badge(
    tree: Tree,
    watered: datetime | None,
    rain: datetime | None,
    specs: list[RuleSpec],
    placeholders: dict,
    now: datetime,
) -> BadgeOut:
    settings = get_settings()
    tz = local_tz()
    water_at, source = last_water(watered, rain, tree.planted_at)
    rule = select_rule(tree.planted_at, now, specs)
    color = compute_badge(water_at, now, rule.interval_days, settings.badge_warn_ratio)
    due = due_at(water_at, rule.interval_days)

    if water_at is None:
        headline, detail = "Sem registro de rega", None
    else:
        verb = "Choveu" if source == "rain" else "Regada"
        headline = f"{verb} {humanize.relative(water_at, now)}"
        detail = humanize.calendar_label(water_at, now, tz)

    recent_rain = source == "rain" and now - water_at < timedelta(hours=RECENT_RAIN_HOURS)
    hint = HINTS[color]
    if source == "rain" and color == BadgeColor.GREEN:
        hint = "Choveu. Não precisa regar agora."

    return BadgeOut(
        color=color,
        headline=headline,
        detail=detail,
        hint=hint,
        last_water_at=water_at,
        last_water_source=source,
        due_at=due,
        due_text=_due_text(color, due, tz),
        last_watering_at=watered,
        last_watering_text=(
            f"{humanize.relative(watered, now)} ({humanize.calendar_label(watered, now, tz)})"
            if watered
            else None
        ),
        recent_rain=bool(recent_rain),
        interval_days=rule.interval_days,
        rule_is_placeholder=placeholders.get(rule.phase, True),
    )


async def tree_badge(session: AsyncSession, tree: Tree, now: datetime) -> BadgeOut:
    return (await badges_for(session, [tree], now))[tree.id]


async def badges_for(session: AsyncSession, trees: list[Tree], now: datetime) -> dict[int, BadgeOut]:
    """Badges for many trees with a fixed number of queries (map, admin list)."""
    trees = [t for t in trees if t.status in WATERABLE]
    if not trees:
        return {}
    rows = await session.execute(
        select(CareEvent.tree_id, func.max(CareEvent.performed_at))
        .where(CareEvent.tree_id.in_([t.id for t in trees]), CareEvent.type == CareEventType.WATERING)
        .group_by(CareEvent.tree_id)
    )
    watered = dict(rows.all())
    rain = await last_rain_at(session, now)
    specs, placeholders = await _rules(session)
    return {t.id: _make_badge(t, watered.get(t.id), rain, specs, placeholders, now) for t in trees}


async def build_tree_out(session: AsyncSession, tree: Tree, now: datetime) -> TreeOut:
    settings = get_settings()
    tz = local_tz()
    planted = tree.status in WATERABLE or (tree.status == TreeStatus.DEAD and tree.planted_at)
    sp = tree.species
    lat, lng = settings.map_center_latlng

    badge = None
    waterings: list[WateringOut] = []
    photos: list[PhotoOut] = []
    if planted:
        if tree.status in WATERABLE:
            badge = await tree_badge(session, tree, now)
        rows = (
            await session.execute(
                select(CareEvent)
                .where(CareEvent.tree_id == tree.id, CareEvent.type == CareEventType.WATERING)
                .order_by(CareEvent.performed_at.desc())
                .limit(10)
            )
        ).scalars()
        waterings = [
            WateringOut(
                performed_at=e.performed_at,
                who=e.performed_by_name or "Alguém",
                when_text=f"{humanize.relative(e.performed_at, now)} · "
                f"{humanize.calendar_label(e.performed_at, now, tz)}",
            )
            for e in rows
        ]
        photo_rows = (
            await session.execute(
                select(Photo).where(Photo.tree_id == tree.id).order_by(Photo.taken_at.asc())
            )
        ).scalars()
        photos = [
            PhotoOut(
                url=media_url(p.file_path),
                taken_at=p.taken_at,
                taken_label=p.taken_at.astimezone(tz).strftime("%d/%m/%Y"),
                caption=p.caption,
            )
            for p in photo_rows
        ]

    return TreeOut(
        public_id=tree.public_id,
        code=tree.code,
        status=tree.status,
        status_label=TREE_STATUS_LABELS[tree.status],
        species=SpeciesOut(
            common_name=sp.common_name,
            scientific_name=sp.scientific_name,
            description=sp.description,
            size_class=sp.size_class,
            root_notes=sp.root_notes,
            fruiting_season=sp.fruiting_season,
            fun_fact=sp.fun_fact,
            photo_url=media_url(sp.photo_path),
            data_review_status=sp.data_review_status,
        ),
        origin=OriginOut(donor_name=tree.origin.donor_name, donated_at=tree.origin.donated_at),
        zone_name=tree.zone.name if tree.zone else None,
        planted_at=tree.planted_at if planted else None,
        age_text=humanize.age(tree.planted_at, now, tz) if planted and tree.planted_at else None,
        location=LocationOut(lat=tree.lat, lng=tree.lng) if planted and tree.lat is not None else None,
        badge=badge,
        can_water=tree.status in WATERABLE,
        min_watering_interval_hours=settings.min_watering_interval_hours,
        recent_waterings=waterings,
        photos=photos,
        map_center=LocationOut(lat=lat, lng=lng),
    )
