from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.time import now_utc
from app.models import CareEvent, Tree
from tests.conftest import tree_id


async def test_list_trees(admin):
    trees = (await admin.get("/api/admin/trees")).json()
    assert len(trees) == 15
    assert trees[0]["code"] == "ARV-001"
    assert trees[0]["public_url"].endswith(f"/a/{trees[0]['public_id']}")


async def test_create_tree_gets_next_code_and_random_public_id(admin, seeded):
    species = (await admin.get("/api/admin/species")).json()
    origin = (await admin.get("/api/admin/origins")).json()[0]
    r = await admin.post("/api/admin/trees", json={"species_id": species[0]["id"], "origin_id": origin["id"]})
    assert r.status_code == 201
    body = r.json()
    assert body["code"] == "ARV-016"
    assert len(body["public_id"]) == 8
    assert body["status"] == "awaiting_planting"


async def test_create_tree_with_unknown_species_404(admin):
    r = await admin.post("/api/admin/trees", json={"species_id": 999, "origin_id": 1})
    assert r.status_code == 404


async def test_plant_tree(admin, seeded):
    tid = await tree_id(seeded, "ARV-001")
    r = await admin.post(
        f"/api/admin/trees/{tid}/plant",
        json={"planted_at": "2026-10-20T09:30:00", "lat": -28.2621, "lng": -52.4059},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "planted"
    assert body["lat"] == -28.2621
    # Naive admin input is São Paulo local time (UTC-3).
    assert datetime.fromisoformat(body["planted_at"]) == datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)
    assert body["badge_color"] == "grey"


async def test_plant_requires_coordinates_and_past_date(admin, seeded):
    tid = await tree_id(seeded, "ARV-001")
    missing = await admin.post(f"/api/admin/trees/{tid}/plant", json={"planted_at": "2026-10-20T09:30:00"})
    future = await admin.post(
        f"/api/admin/trees/{tid}/plant",
        json={"planted_at": (now_utc() + timedelta(days=2)).isoformat(), "lat": -28.26, "lng": -52.40},
    )
    out_of_range = await admin.post(
        f"/api/admin/trees/{tid}/plant", json={"planted_at": "2026-10-20T09:30:00", "lat": -128, "lng": 0}
    )
    assert missing.status_code == future.status_code == out_of_range.status_code == 422


async def test_patch_status_planted_without_date_is_rejected(admin, seeded):
    tid = await tree_id(seeded, "ARV-002")
    r = await admin.patch(f"/api/admin/trees/{tid}", json={"status": "planted"})
    assert r.status_code == 422
    assert "data de plantio" in r.json()["detail"]


async def test_patch_attention_and_undo_planting(admin, seeded):
    tid = await tree_id(seeded, "ARV-001")
    await admin.post(f"/api/admin/trees/{tid}/plant", json={"planted_at": "2026-10-20T09:30:00", "lat": -28.26, "lng": -52.4})
    attention = await admin.patch(f"/api/admin/trees/{tid}", json={"status": "attention", "notes": "Folhas secas"})
    assert attention.json()["status"] == "attention"
    undo = await admin.patch(f"/api/admin/trees/{tid}", json={"status": "awaiting_planting"})
    assert undo.json()["status"] == "awaiting_planting" and undo.json()["planted_at"] is None


async def test_delete_only_awaiting_without_history(admin, seeded):
    awaiting = await tree_id(seeded, "ARV-002")
    planted = await tree_id(seeded, "ARV-001")
    await admin.post(f"/api/admin/trees/{planted}/plant", json={"planted_at": "2026-10-20T09:30:00", "lat": -28.26, "lng": -52.4})
    assert (await admin.delete(f"/api/admin/trees/{planted}")).status_code == 409
    assert (await admin.delete(f"/api/admin/trees/{awaiting}")).status_code == 204
    assert await seeded.scalar(select(Tree.id).where(Tree.id == awaiting)) is None


async def test_admin_care_event_and_spam_removal(admin, seeded):
    tid = await tree_id(seeded, "ARV-001")
    await admin.post(f"/api/admin/trees/{tid}/plant", json={"planted_at": "2026-10-20T09:30:00", "lat": -28.26, "lng": -52.4})
    r = await admin.post(f"/api/admin/trees/{tid}/care-events", json={"type": "fertilizing", "notes": "Adubo orgânico"})
    assert r.status_code == 201 and r.json()["source"] == "admin"
    events = (await admin.get(f"/api/admin/trees/{tid}/care-events")).json()
    assert len(events) == 1
    assert (await admin.delete(f"/api/admin/trees/{tid}/care-events/{events[0]['id']}")).status_code == 204
    assert (await seeded.execute(select(CareEvent))).first() is None


async def test_species_crud_and_review(admin):
    created = await admin.post("/api/admin/species", json={"common_name": "Pitangueira", "scientific_name": " "})
    assert created.status_code == 201
    sid = created.json()["id"]
    assert created.json()["scientific_name"] is None  # blank -> null, shown as "em revisão"
    patched = await admin.patch(
        f"/api/admin/species/{sid}", json={"scientific_name": "Eugenia uniflora", "data_review_status": "reviewed"}
    )
    assert patched.json()["data_review_status"] == "reviewed"
    dup = await admin.post("/api/admin/species", json={"common_name": "Pitangueira"})
    assert dup.status_code == 422
    assert (await admin.delete(f"/api/admin/species/{sid}")).status_code == 204


async def test_species_with_trees_cannot_be_deleted(admin):
    species = (await admin.get("/api/admin/species")).json()
    araca = next(s for s in species if s["common_name"] == "Araçá")
    assert araca["tree_count"] == 5
    assert (await admin.delete(f"/api/admin/species/{araca['id']}")).status_code == 409


async def test_origin_donation_date(admin, make_client, seeded):
    origin = (await admin.get("/api/admin/origins")).json()[0]
    r = await admin.patch(f"/api/admin/origins/{origin['id']}", json={"donated_at": "2026-09-15"})
    assert r.json()["donated_at"] == "2026-09-15"
    pid = await seeded.scalar(select(Tree.public_id).where(Tree.code == "ARV-003"))
    async with make_client() as c:
        public = (await c.get(f"/api/trees/{pid}")).json()
    assert public["origin"]["donated_at"] == "2026-09-15"
