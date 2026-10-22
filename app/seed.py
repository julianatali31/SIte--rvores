"""Idempotent seed: safe to run more than once.

Run with: python -m app.seed
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ids import new_public_id, tree_code
from app.core.security import hash_password
from app.models import Origin, PlantingZone, Species, Tree, User, WateringRule
from app.models.enums import DataReviewStatus, TreeStatus, WateringPhase

DONOR_NAME = "Vale Natural Garden Center"
ZONE_1_NAME = "Zona 1 — Lago"

# Only common + probable scientific name. Botanical fields stay empty on purpose:
# the UI shows "informação em revisão" until someone reviews them.
SPECIES = [
    ("Araçá", "Psidium cattleianum"),
    ("Cereja-do-mato", "Eugenia involucrata"),
    ("Guabiju", "Myrcianthes pungens"),
]

# (first, last) tree number per species, in SPECIES order.
TREE_RANGES = {"Araçá": (1, 5), "Cereja-do-mato": (6, 10), "Guabiju": (11, 15)}
BATCH_1_CODES = {"ARV-001", "ARV-006", "ARV-007", "ARV-011"}

ZONE_1_DESCRIPTION = "Área entre o lago, o muro e o acesso à quadra."
ZONE_1_RESTRICTIONS = (
    "Manter a via livre. Recuo mínimo de 5 m do muro. "
    "Capacidade estimada pelo engenheiro do campus: até 3 árvores de grande porte "
    "ou até 6 de menor porte."
)

PLACEHOLDER_NOTE = "PLACEHOLDER — CONFIRMAR COM NUGAI/ENGENHARIA"
# Values exist only so the badge logic can run. They are NOT agronomic guidance.
WATERING_RULES = [
    (WateringPhase.NEWLY_PLANTED, 2.0, 90),
    (WateringPhase.ESTABLISHED, 7.0, None),
]


async def _get_or_create(session: AsyncSession, model, lookup: dict, defaults: dict):
    obj = (await session.execute(select(model).filter_by(**lookup))).scalar_one_or_none()
    if obj is None:
        obj = model(**lookup, **defaults)
        session.add(obj)
        await session.flush()
    return obj


async def _unique_public_id(session: AsyncSession) -> str:
    while True:
        candidate = new_public_id()
        exists = await session.scalar(select(Tree.id).where(Tree.public_id == candidate))
        if exists is None:
            return candidate


async def seed(session: AsyncSession) -> None:
    settings = get_settings()

    species_by_name = {}
    for common, scientific in SPECIES:
        species_by_name[common] = await _get_or_create(
            session,
            Species,
            {"common_name": common},
            {"scientific_name": scientific, "data_review_status": DataReviewStatus.PENDING},
        )

    origin = await _get_or_create(
        session,
        Origin,
        {"donor_name": DONOR_NAME},
        # Donation date unknown at seed time: filled in by the admin.
        {"seedling_count": 15, "donated_at": None, "notes": "5 araçá, 5 cereja-do-mato, 5 guabiju."},
    )

    zone = await _get_or_create(
        session,
        PlantingZone,
        {"name": ZONE_1_NAME},
        {
            "description": ZONE_1_DESCRIPTION,
            "restrictions": ZONE_1_RESTRICTIONS,
            "polygon_geojson": None,
        },
    )

    for common, (first, last) in TREE_RANGES.items():
        for number in range(first, last + 1):
            code = tree_code(number)
            exists = await session.scalar(select(Tree.id).where(Tree.code == code))
            if exists is not None:
                continue
            in_batch_1 = code in BATCH_1_CODES
            session.add(
                Tree(
                    code=code,
                    public_id=await _unique_public_id(session),
                    species_id=species_by_name[common].id,
                    origin_id=origin.id,
                    zone_id=zone.id if in_batch_1 else None,
                    planting_batch=1 if in_batch_1 else None,
                    status=TreeStatus.AWAITING_PLANTING,
                )
            )
            await session.flush()

    for phase, interval, until in WATERING_RULES:
        await _get_or_create(
            session,
            WateringRule,
            {"phase": phase},
            {
                "interval_days": interval,
                "phase_until_days": until,
                "is_placeholder": True,
                "note": PLACEHOLDER_NOTE,
            },
        )

    if settings.admin_username and settings.admin_password:
        await _get_or_create(
            session,
            User,
            {"username": settings.admin_username},
            {"password_hash": hash_password(settings.admin_password)},
        )

    await session.commit()


async def _main() -> None:
    from app.core.db import SessionLocal, engine

    async with SessionLocal() as session:
        await seed(session)
    await engine.dispose()
    print("Seed concluído.")


if __name__ == "__main__":
    asyncio.run(_main())
