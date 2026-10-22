from datetime import timedelta

from app.core.time import now_utc
from tests.conftest import tree_id
from tests.factories import add_watering, plant

SQUARE = [[-52.4065, -28.2625], [-52.4055, -28.2625], [-52.4055, -28.2615], [-52.4065, -28.2615], [-52.4065, -28.2625]]


async def test_map_page_served(seeded, make_client):
    async with make_client() as c:
        page = await c.get("/mapa")
        home = await c.get("/")
    assert page.status_code == 200 and 'type="module"' in page.text
    assert home.status_code in (302, 307) and home.headers["location"] == "/mapa"


async def test_map_lists_only_planted_trees_with_badge_color(seeded, make_client):
    t1 = await plant(seeded, "ARV-001", lat=-28.2620, lng=-52.4060)
    t6 = await plant(seeded, "ARV-006", lat=-28.2621, lng=-52.4061)
    await add_watering(seeded, t1, now_utc() - timedelta(hours=2))
    await add_watering(seeded, t6, now_utc() - timedelta(days=5))
    t6.notes = "nota interna"
    await seeded.commit()
    async with make_client() as c:
        data = (await c.get("/api/map/trees")).json()
    assert data["type"] == "FeatureCollection"
    by_code = {f["properties"]["code"]: f for f in data["features"]}
    assert set(by_code) == {"ARV-001", "ARV-006"}  # awaiting trees never on the map
    assert by_code["ARV-001"]["geometry"] == {"type": "Point", "coordinates": [-52.4060, -28.2620]}
    assert by_code["ARV-001"]["properties"]["badge_color"] == "green"
    assert by_code["ARV-006"]["properties"]["badge_color"] == "red"
    assert by_code["ARV-001"]["properties"]["url"] == f"/a/{t1.public_id}"
    assert "nota interna" not in str(data)


async def test_attention_trees_stay_on_map_dead_trees_do_not(seeded, make_client):
    t1 = await plant(seeded, "ARV-001")
    t6 = await plant(seeded, "ARV-006")
    t1.status, t6.status = "attention", "dead"
    await seeded.commit()
    async with make_client() as c:
        codes = [f["properties"]["code"] for f in (await c.get("/api/map/trees")).json()["features"]]
    assert codes == ["ARV-001"]


async def test_map_badges_match_tree_page(seeded, make_client):
    tree = await plant(seeded, "ARV-007")
    await add_watering(seeded, tree, now_utc() - timedelta(hours=40))
    async with make_client() as c:
        feature = (await c.get("/api/map/trees")).json()["features"][0]["properties"]
        page = (await c.get(f"/api/trees/{tree.public_id}")).json()["badge"]
    assert feature["badge_color"] == page["color"] == "yellow"
    assert feature["badge_headline"] == page["headline"]


async def test_map_zones_only_with_polygon(admin, seeded, make_client):
    async with make_client() as c:
        assert (await c.get("/api/map/zones")).json()["features"] == []
    zid = (await admin.get("/api/admin/zones")).json()[0]["id"]
    await admin.put(f"/api/admin/zones/{zid}/geojson", json={"type": "Polygon", "coordinates": [SQUARE]})
    async with make_client() as c:
        features = (await c.get("/api/map/zones")).json()["features"]
    assert len(features) == 1
    assert features[0]["properties"]["name"] == "Zona 1 — Lago"
    assert features[0]["geometry"]["type"] == "Polygon"


async def test_admin_list_uses_same_badges(admin, seeded):
    tid = await tree_id(seeded, "ARV-001")
    await admin.post(f"/api/admin/trees/{tid}/plant", json={"planted_at": "2026-10-01T09:00:00", "lat": -28.26, "lng": -52.4})
    trees = {t["code"]: t for t in (await admin.get("/api/admin/trees")).json()}
    assert trees["ARV-001"]["badge_color"] == "grey"
    assert trees["ARV-002"]["badge_color"] is None
