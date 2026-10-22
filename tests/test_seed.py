from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.security import verify_password
from app.models import Origin, PlantingZone, Species, Tree, User, WateringRule
from app.models.enums import DataReviewStatus, TreeStatus
from app.seed import seed


async def _trees(session):
    result = await session.execute(
        select(Tree).options(selectinload(Tree.species), selectinload(Tree.zone)).order_by(Tree.code)
    )
    return result.scalars().all()


async def test_seed_creates_15_trees_with_code_rule(session):
    await seed(session)
    trees = await _trees(session)
    assert [t.code for t in trees] == [f"ARV-{n:03d}" for n in range(1, 16)]
    by_species = {t.code: t.species.common_name for t in trees}
    assert {by_species[f"ARV-{n:03d}"] for n in range(1, 6)} == {"Araçá"}
    assert {by_species[f"ARV-{n:03d}"] for n in range(6, 11)} == {"Cereja-do-mato"}
    assert {by_species[f"ARV-{n:03d}"] for n in range(11, 16)} == {"Guabiju"}


async def test_seed_batch_1_in_zone_1_and_all_awaiting(session):
    await seed(session)
    trees = await _trees(session)
    batch_1 = {t.code for t in trees if t.planting_batch == 1}
    assert batch_1 == {"ARV-001", "ARV-006", "ARV-007", "ARV-011"}
    for t in trees:
        assert t.status == TreeStatus.AWAITING_PLANTING
        assert t.planted_at is None
        if t.code in batch_1:
            assert t.zone.name == "Zona 1 — Lago"
        else:
            assert t.zone_id is None and t.planting_batch is None


async def test_seed_all_trees_trace_to_donor(session):
    await seed(session)
    origin = (await session.execute(select(Origin))).scalar_one()
    assert origin.donor_name == "Vale Natural Garden Center"
    assert origin.seedling_count == 15
    assert origin.donated_at is None  # unknown: not invented
    count = await session.scalar(select(func.count()).where(Tree.origin_id == origin.id))
    assert count == 15


async def test_seed_species_pending_without_invented_botany(session):
    await seed(session)
    species = (await session.execute(select(Species))).scalars().all()
    assert {s.scientific_name for s in species} == {
        "Psidium cattleianum",
        "Eugenia involucrata",
        "Myrcianthes pungens",
    }
    for s in species:
        assert s.data_review_status == DataReviewStatus.PENDING
        assert s.description is None and s.fruiting_season is None and s.fun_fact is None


async def test_seed_zone_1_without_polygon(session):
    await seed(session)
    zone = (await session.execute(select(PlantingZone))).scalar_one()
    assert zone.polygon_geojson is None
    assert "5 m do muro" in zone.restrictions


async def test_seed_watering_rules_are_placeholders(session):
    await seed(session)
    rules = (await session.execute(select(WateringRule))).scalars().all()
    assert len(rules) == 2
    assert all(r.is_placeholder and "CONFIRMAR COM NUGAI/ENGENHARIA" in r.note for r in rules)


async def test_seed_admin_password_is_hashed(session):
    await seed(session)
    user = (await session.execute(select(User))).scalar_one()
    assert user.password_hash.startswith("$argon2")
    assert verify_password(user.password_hash, "test-password-123")
    assert not verify_password(user.password_hash, "wrong")


async def test_seed_is_idempotent(session):
    await seed(session)
    ids_before = {t.code: t.public_id for t in await _trees(session)}
    await seed(session)
    ids_after = {t.code: t.public_id for t in await _trees(session)}
    assert ids_before == ids_after
    assert await session.scalar(select(func.count()).select_from(Species)) == 3


async def test_public_ids_unique_and_unrelated_to_code(session):
    await seed(session)
    trees = await _trees(session)
    pids = [t.public_id for t in trees]
    assert len(set(pids)) == 15
    assert all(t.code.lower() not in t.public_id for t in trees)
