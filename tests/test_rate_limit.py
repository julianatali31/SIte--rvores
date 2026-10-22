from datetime import timedelta

from sqlalchemy import func, select

from app.core.time import now_utc
from app.models import CareEvent
from tests.factories import add_watering, plant


async def test_min_interval_blocks_second_watering_same_tree(seeded, make_client):
    tree = await plant(seeded, "ARV-001")
    async with make_client(ip="203.0.113.1") as a, make_client(ip="203.0.113.2") as b:
        first = await a.post(f"/api/trees/{tree.public_id}/waterings", json={})
        second = await b.post(f"/api/trees/{tree.public_id}/waterings", json={})
    assert first.status_code == 201
    assert second.status_code == 409
    assert "já foi regada às" in second.json()["detail"]
    assert second.json()["tree"]["badge"]["color"] == "green"  # UI can still refresh the badge
    assert await seeded.scalar(select(func.count()).select_from(CareEvent)) == 1


async def test_min_interval_allows_after_gap(seeded, make_client):
    tree = await plant(seeded, "ARV-001")
    await add_watering(seeded, tree, now_utc() - timedelta(hours=3, minutes=1))
    async with make_client() as c:
        r = await c.post(f"/api/trees/{tree.public_id}/waterings", json={})
    assert r.status_code == 201


async def test_min_interval_is_configurable(seeded, make_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "min_watering_interval_hours", 6)
    tree = await plant(seeded, "ARV-001")
    await add_watering(seeded, tree, now_utc() - timedelta(hours=4))
    async with make_client() as c:
        r = await c.post(f"/api/trees/{tree.public_id}/waterings", json={})
    assert r.status_code == 409


async def test_rate_limit_per_ip(seeded, make_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "watering_rate_limit_count", 2)
    trees = [await plant(seeded, code) for code in ("ARV-001", "ARV-006", "ARV-007")]
    async with make_client(ip="203.0.113.50") as same_ip, make_client(ip="203.0.113.51") as other_ip:
        r1 = await same_ip.post(f"/api/trees/{trees[0].public_id}/waterings", json={})
        r2 = await same_ip.post(f"/api/trees/{trees[1].public_id}/waterings", json={})
        r3 = await same_ip.post(f"/api/trees/{trees[2].public_id}/waterings", json={})
        r4 = await other_ip.post(f"/api/trees/{trees[2].public_id}/waterings", json={})
    assert [r1.status_code, r2.status_code, r3.status_code] == [201, 201, 429]
    assert int(r3.headers["retry-after"]) > 0
    assert r4.status_code == 201  # another IP is not affected


async def test_rate_limit_window_expires(seeded, make_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "watering_rate_limit_count", 1)
    trees = [await plant(seeded, code) for code in ("ARV-001", "ARV-006")]
    async with make_client(ip="203.0.113.60") as c:
        assert (await c.post(f"/api/trees/{trees[0].public_id}/waterings", json={})).status_code == 201
        # Age the event past the window.
        event = (await seeded.execute(select(CareEvent))).scalar_one()
        event.created_at = now_utc() - timedelta(minutes=61)
        await seeded.commit()
        assert (await c.post(f"/api/trees/{trees[1].public_id}/waterings", json={})).status_code == 201
