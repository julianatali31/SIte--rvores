from sqlalchemy import select

from app.models import Tree
from tests.conftest import tree_id

SQUARE = [[-52.4065, -28.2625], [-52.4055, -28.2625], [-52.4055, -28.2615], [-52.4065, -28.2615], [-52.4065, -28.2625]]


async def _zone_id(admin):
    return (await admin.get("/api/admin/zones")).json()[0]["id"]


async def test_draw_polygon_via_patch(admin):
    zid = await _zone_id(admin)
    r = await admin.patch(f"/api/admin/zones/{zid}", json={"polygon_geojson": {"type": "Polygon", "coordinates": [SQUARE]}})
    assert r.status_code == 200
    assert r.json()["polygon_geojson"]["coordinates"][0] == SQUARE
    cleared = await admin.patch(f"/api/admin/zones/{zid}", json={"polygon_geojson": None})
    assert cleared.json()["polygon_geojson"] is None


async def test_import_feature_collection(admin):
    zid = await _zone_id(admin)
    fc = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"name": "x"},
                      "geometry": {"type": "Polygon", "coordinates": [[p + [123.0] for p in SQUARE]]}}],
    }
    r = await admin.put(f"/api/admin/zones/{zid}/geojson", json=fc)
    assert r.status_code == 200, r.text
    assert r.json()["polygon_geojson"] == {"type": "Polygon", "coordinates": [SQUARE]}  # altitude dropped


async def test_import_rejects_invalid_geojson(admin):
    zid = await _zone_id(admin)
    cases = [
        {"type": "LineString", "coordinates": SQUARE},
        {"type": "Polygon", "coordinates": [SQUARE[:-1]]},  # not closed
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 0]]]},  # too few points
        {"type": "Polygon", "coordinates": [[[-252, 0], [1, 1], [1, 0], [-252, 0]]]},  # out of range
        {"type": "FeatureCollection", "features": []},
        {"type": "Polygon", "coordinates": [[["a", "b"], [1, 1], [1, 0], ["a", "b"]]]},
    ]
    for case in cases:
        r = await admin.put(f"/api/admin/zones/{zid}/geojson", json=case)
        assert r.status_code == 422, case


async def test_rain_updates_public_badge(admin, make_client, seeded):
    tid = await tree_id(seeded, "ARV-001")
    await admin.post(f"/api/admin/trees/{tid}/plant", json={"planted_at": "2026-10-01T09:00:00", "lat": -28.26, "lng": -52.4})
    r = await admin.post("/api/admin/rain-events", json={"precipitation_mm": 15.5, "notes": "Temporal à tarde"})
    assert r.status_code == 201 and r.json()["source"] == "manual"
    pid = await seeded.scalar(select(Tree.public_id).where(Tree.id == tid))
    async with make_client() as c:
        badge = (await c.get(f"/api/trees/{pid}")).json()["badge"]
    assert badge["last_water_source"] == "rain" and badge["color"] == "green"
    assert (await admin.delete(f"/api/admin/rain-events/{r.json()['id']}")).status_code == 204


async def test_rain_in_future_rejected(admin):
    r = await admin.post("/api/admin/rain-events", json={"occurred_at": "2999-01-01T10:00:00"})
    assert r.status_code == 422


async def test_watering_rules_can_be_confirmed(admin):
    rules = (await admin.get("/api/admin/watering-rules")).json()
    assert all(r["is_placeholder"] for r in rules)
    r = await admin.patch(f"/api/admin/watering-rules/{rules[0]['id']}", json={"interval_days": 3, "is_placeholder": False})
    assert r.json()["interval_days"] == 3 and r.json()["is_placeholder"] is False
