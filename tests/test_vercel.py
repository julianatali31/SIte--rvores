"""Serverless (Vercel + Neon + Blob) adaptations."""
import io

import pytest
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.pool import NullPool

from app.core.config import Settings, normalize_database_url
from app.core.db import build_engine
from app.models import LoginAttempt
from tests.conftest import tree_id

STRONG = "x" * 32


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (
            "postgresql://u:p@ep-x-pooler.sa-east-1.aws.neon.tech/arvores?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x-pooler.sa-east-1.aws.neon.tech/arvores?ssl=require",
        ),
        ("postgres://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        ("postgresql+asyncpg://u:p@localhost/db", "postgresql+asyncpg://u:p@localhost/db"),
    ],
)
def test_normalize_database_url(given, expected):
    assert normalize_database_url(given) == expected


def test_production_requires_real_secrets():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", secret_key=STRONG)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, vercel_env="production", ip_hash_salt=STRONG)
    ok = Settings(_env_file=None, vercel_env="production", secret_key=STRONG, ip_hash_salt=STRONG)
    assert ok.is_production
    preview = Settings(_env_file=None, vercel=True, vercel_env="preview")
    assert preview.serverless and not preview.is_production


def test_serverless_engine_has_no_pool_and_no_statement_cache():
    settings = Settings(_env_file=None, vercel=True, database_url="postgresql://u:p@h/db?sslmode=require")
    engine = build_engine(settings)
    assert isinstance(engine.pool, NullPool)
    assert engine.url.query["prepared_statement_cache_size"] == "0"
    assert engine.url.query["ssl"] == "require"


def test_storage_backend_selection():
    assert Settings(_env_file=None).storage_backend == "local"
    assert Settings(_env_file=None, blob_read_write_token="vercel_blob_rw_x").storage_backend == "blob"


async def test_client_ip_from_vercel_headers(seeded, make_client, settings, monkeypatch):
    """On Vercel the real IP comes from x-real-ip; two people behind the edge are two keys."""
    from tests.factories import plant

    monkeypatch.setattr(settings, "vercel", True)
    monkeypatch.setattr(settings, "watering_rate_limit_count", 1)
    trees = [await plant(seeded, code) for code in ("ARV-001", "ARV-006", "ARV-007")]
    async with make_client(ip="10.0.0.1") as c:  # same edge address for everyone
        a = await c.post(f"/api/trees/{trees[0].public_id}/waterings", json={}, headers={"x-real-ip": "200.1.1.1"})
        b = await c.post(f"/api/trees/{trees[1].public_id}/waterings", json={}, headers={"x-real-ip": "200.2.2.2"})
        again = await c.post(f"/api/trees/{trees[2].public_id}/waterings", json={}, headers={"x-real-ip": "200.1.1.1"})
    assert [a.status_code, b.status_code, again.status_code] == [201, 201, 429]


async def test_forwarded_headers_ignored_outside_vercel(seeded, make_client, settings, monkeypatch):
    """Off Vercel a client cannot dodge the limit by inventing x-forwarded-for."""
    from tests.factories import plant

    monkeypatch.setattr(settings, "watering_rate_limit_count", 1)
    trees = [await plant(seeded, code) for code in ("ARV-001", "ARV-006")]
    async with make_client(ip="203.0.113.77") as c:
        a = await c.post(f"/api/trees/{trees[0].public_id}/waterings", json={}, headers={"x-forwarded-for": "1.1.1.1"})
        b = await c.post(f"/api/trees/{trees[1].public_id}/waterings", json={}, headers={"x-forwarded-for": "2.2.2.2"})
    assert [a.status_code, b.status_code] == [201, 429]


async def test_login_lockout_is_stored_in_db(seeded, make_client):
    async with make_client(ip="198.51.100.9") as c:
        for _ in range(2):
            await c.post("/api/admin/login", json={"username": "admin", "password": "x"})
        assert await seeded.scalar(select(func.count()).select_from(LoginAttempt)) == 2
        ok = await c.post("/api/admin/login", json={"username": "admin", "password": "test-password-123"})
    assert ok.status_code == 200
    assert await seeded.scalar(select(func.count()).select_from(LoginAttempt)) == 0  # cleared on success


@pytest.fixture
def fake_blob(settings, monkeypatch):
    import vercel.blob as blob

    store: dict[str, bytes] = {}

    class Result:
        def __init__(self, url):
            self.url = url

    async def put_blob(pathname, body, *, access, content_type=None, cache_control_max_age=None, **kw):
        assert access == "public" and content_type == "image/jpeg"
        url = f"https://abc123.public.blob.vercel-storage.com/{pathname}"
        store[url] = bytes(body)
        return Result(url)

    async def delete_blob(url, **kw):
        store.pop(url, None)

    monkeypatch.setattr(blob, "put_blob", put_blob)
    monkeypatch.setattr(blob, "delete_blob", delete_blob)
    monkeypatch.setattr(settings, "blob_read_write_token", "vercel_blob_rw_test")
    return store


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (20, 120, 40)).save(buf, format="JPEG")
    return buf.getvalue()


async def test_photos_go_to_blob(admin, seeded, make_client, fake_blob, _tmp_uploads):
    tid = await tree_id(seeded, "ARV-001")
    await admin.post(f"/api/admin/trees/{tid}/plant", json={"planted_at": "2026-10-20T09:30:00", "lat": -28.26, "lng": -52.4})
    r = await admin.post(f"/api/admin/trees/{tid}/photos", files={"file": ("f.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 201, r.text
    url = r.json()["url"]
    assert url.startswith("https://abc123.public.blob.vercel-storage.com/trees/") and url in fake_blob
    assert not _tmp_uploads.exists() or not any(_tmp_uploads.rglob("*.jpg"))  # nothing on local disk

    pid = (await admin.get(f"/api/admin/trees/{tid}")).json()["public_id"]
    async with make_client() as c:
        public = await c.get(f"/api/trees/{pid}")
    assert public.json()["photos"][0]["url"] == url
    assert "blob.vercel-storage.com" in public.headers["content-security-policy"]

    assert (await admin.delete(f"/api/admin/trees/{tid}/photos/{r.json()['id']}")).status_code == 204
    assert url not in fake_blob


async def test_config_exposes_upload_limit(seeded, make_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 4)
    async with make_client() as c:
        assert (await c.get("/api/config")).json()["max_upload_mb"] == 4
