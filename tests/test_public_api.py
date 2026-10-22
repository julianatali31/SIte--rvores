from datetime import timedelta

from sqlalchemy import func, select

from app.core.time import now_utc
from app.models import CareEvent, Tree
from tests.factories import add_rain, add_watering, plant


async def _pid(session, code):
    return await session.scalar(select(Tree.public_id).where(Tree.code == code))


async def test_unknown_tree_404(seeded, make_client):
    async with make_client() as c:
        assert (await c.get("/api/trees/zzzzzzzz")).status_code == 404
        assert (await c.get("/api/trees/../etc")).status_code == 404
        assert (await c.get("/a/zzzzzzzz")).status_code == 404


async def test_awaiting_tree_has_no_badge(seeded, make_client):
    pid = await _pid(seeded, "ARV-002")
    async with make_client() as c:
        r = await c.get(f"/api/trees/{pid}")
        page = await c.get(f"/a/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "awaiting_planting"
    assert body["badge"] is None and body["can_water"] is False
    assert body["origin"]["donor_name"] == "Vale Natural Garden Center"
    assert body["species"]["description"] is None  # UI shows "informação em revisão"
    assert page.status_code == 200 and 'type="module"' in page.text
    assert r.headers["cache-control"] == "no-store"


async def test_awaiting_tree_rejects_watering(seeded, make_client):
    pid = await _pid(seeded, "ARV-002")
    async with make_client() as c:
        r = await c.post(f"/api/trees/{pid}/waterings", json={})
    assert r.status_code == 409
    assert await seeded.scalar(select(func.count()).select_from(CareEvent)) == 0


async def test_planted_tree_without_record_is_grey(seeded, make_client):
    await plant(seeded, "ARV-001", days_ago=12)
    pid = await _pid(seeded, "ARV-001")
    async with make_client() as c:
        body = (await c.get(f"/api/trees/{pid}")).json()
    assert body["age_text"] == "plantada há 12 dias"
    assert body["badge"]["color"] == "grey"
    assert body["badge"]["headline"] == "Sem registro de rega"
    assert body["badge"]["rule_is_placeholder"] is True
    assert body["location"] == {"lat": -28.26, "lng": -52.40}


async def test_watering_turns_badge_green(seeded, make_client):
    await plant(seeded, "ARV-001")
    pid = await _pid(seeded, "ARV-001")
    async with make_client() as c:
        r = await c.post(f"/api/trees/{pid}/waterings", json={"name": "  Ana   Paula "})
    assert r.status_code == 201
    body = r.json()
    assert body["message"] == "Obrigado, Ana Paula! Rega registrada."
    assert body["tree"]["badge"]["color"] == "green"
    assert body["tree"]["badge"]["headline"] == "Regada agora mesmo"
    assert body["tree"]["badge"]["due_text"].startswith("Próxima rega até")
    assert body["tree"]["recent_waterings"][0]["who"] == "Ana Paula"


async def test_overdue_tree_is_red(seeded, make_client):
    tree = await plant(seeded, "ARV-006", days_ago=10)
    await add_watering(seeded, tree, now_utc() - timedelta(days=3))  # placeholder rule: 2 days
    async with make_client() as c:
        badge = (await c.get(f"/api/trees/{tree.public_id}")).json()["badge"]
    assert badge["color"] == "red"
    assert badge["headline"] == "Regada há 3 dias"
    assert badge["due_text"].startswith("Rega atrasada desde")


async def test_rain_counts_as_last_water(seeded, make_client):
    tree = await plant(seeded, "ARV-007", days_ago=10)
    await add_watering(seeded, tree, now_utc() - timedelta(days=4))
    await add_rain(seeded, now_utc() - timedelta(hours=5), mm=12)
    async with make_client() as c:
        badge = (await c.get(f"/api/trees/{tree.public_id}")).json()["badge"]
    assert badge["color"] == "green"
    assert badge["last_water_source"] == "rain"
    assert badge["headline"] == "Choveu há 5 h"
    assert badge["recent_rain"] is True
    assert badge["last_watering_text"].startswith("há 4 dias")


async def test_rain_before_planting_does_not_count(seeded, make_client):
    tree = await plant(seeded, "ARV-011", days_ago=1)
    await add_rain(seeded, now_utc() - timedelta(days=3))
    async with make_client() as c:
        badge = (await c.get(f"/api/trees/{tree.public_id}")).json()["badge"]
    assert badge["color"] == "grey"


async def test_honeypot_is_not_stored(seeded, make_client):
    await plant(seeded, "ARV-001")
    pid = await _pid(seeded, "ARV-001")
    async with make_client() as c:
        r = await c.post(f"/api/trees/{pid}/waterings", json={"website": "http://spam.example"})
    assert r.status_code == 201  # looks like success to the bot
    assert await seeded.scalar(select(func.count()).select_from(CareEvent)) == 0


async def test_name_validation(seeded, make_client):
    await plant(seeded, "ARV-001")
    pid = await _pid(seeded, "ARV-001")
    async with make_client() as c:
        too_long = await c.post(f"/api/trees/{pid}/waterings", json={"name": "x" * 61})
        bad_type = await c.post(f"/api/trees/{pid}/waterings", json={"name": 123})
        blank = await c.post(f"/api/trees/{pid}/waterings", json={"name": "  \n\t "})
    assert too_long.status_code == 422
    assert bad_type.status_code == 422
    assert blank.status_code == 201
    assert blank.json()["tree"]["recent_waterings"][0]["who"] == "Alguém"


async def test_ip_is_hashed_never_stored_raw(seeded, make_client):
    await plant(seeded, "ARV-001")
    pid = await _pid(seeded, "ARV-001")
    async with make_client(ip="198.51.100.7") as c:
        await c.post(f"/api/trees/{pid}/waterings", json={})
    event = (await seeded.execute(select(CareEvent))).scalar_one()
    assert event.ip_hash and len(event.ip_hash) == 64
    assert "198.51.100.7" not in event.ip_hash
    for value in vars(event).values():
        assert "198.51.100.7" not in str(value)


async def test_dead_tree_page_payload(seeded, make_client):
    tree = await plant(seeded, "ARV-001")
    tree.status = "dead"
    await seeded.commit()
    async with make_client() as c:
        body = (await c.get(f"/api/trees/{tree.public_id}")).json()
        post = await c.post(f"/api/trees/{tree.public_id}/waterings", json={})
    assert body["badge"] is None and body["can_water"] is False
    assert post.status_code == 409


async def test_security_headers(seeded, make_client):
    async with make_client() as c:
        r = await c.get("/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
