from datetime import timedelta

import jwt
import pytest

from app.core.time import now_utc

PROTECTED = [
    ("GET", "/api/admin/trees"),
    ("POST", "/api/admin/trees"),
    ("GET", "/api/admin/species"),
    ("PATCH", "/api/admin/zones/1"),
    ("PUT", "/api/admin/zones/1/geojson"),
    ("POST", "/api/admin/rain-events"),
    ("GET", "/api/admin/watering-rules"),
    ("GET", "/api/admin/labels.pdf"),
    ("GET", "/api/admin/trees/1/qr.png"),
    ("POST", "/api/admin/trees/1/plant"),
]


async def test_login_ok_and_me(admin):
    r = await admin.get("/api/admin/me")
    assert r.status_code == 200 and r.json() == {"username": "admin"}


async def test_login_wrong_password(seeded, make_client):
    async with make_client() as c:
        r = await c.post("/api/admin/login", json={"username": "admin", "password": "nope"})
        unknown = await c.post("/api/admin/login", json={"username": "ghost", "password": "nope"})
    assert r.status_code == 401 and unknown.status_code == 401
    assert r.json()["detail"] == unknown.json()["detail"]  # does not reveal which part was wrong


@pytest.mark.parametrize(("method", "path"), PROTECTED)
async def test_admin_routes_require_token(seeded, make_client, method, path):
    async with make_client() as c:
        r = await c.request(method, path, json={})
    assert r.status_code == 401


async def test_invalid_and_expired_tokens(seeded, make_client, settings):
    expired = jwt.encode(
        {"sub": "1", "exp": now_utc() - timedelta(minutes=1)}, settings.secret_key, algorithm="HS256"
    )
    forged = jwt.encode({"sub": "1", "exp": now_utc() + timedelta(hours=1)}, "wrong-secret-key-xxxxx", algorithm="HS256")
    async with make_client() as c:
        for token in (expired, forged, "garbage"):
            r = await c.get("/api/admin/trees", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 401


async def test_login_lockout_after_repeated_failures(seeded, make_client):
    async with make_client(ip="198.51.100.200") as c:
        for _ in range(5):
            assert (await c.post("/api/admin/login", json={"username": "admin", "password": "x"})).status_code == 401
        blocked = await c.post("/api/admin/login", json={"username": "admin", "password": "test-password-123"})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
