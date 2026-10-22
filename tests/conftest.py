import asyncio
import os

# Must be set before any app module reads settings.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/arvores_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-password-123")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.models import Base  # noqa: E402


async def _reset_schema() -> None:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Fresh schema built by the real Alembic migrations, not create_all."""
    asyncio.run(_reset_schema())
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(cfg, "head")
    yield


@pytest.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    async with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await engine.dispose()


@pytest.fixture
async def seeded(session):
    from app.seed import seed

    await seed(session)
    return session


@pytest.fixture
def make_client(session):
    """Factory for an HTTP client bound to the test session, with a chosen client IP."""
    from httpx import ASGITransport, AsyncClient

    from app.core.db import get_session
    from app.main import app

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    clients = []

    def _make(ip: str = "203.0.113.10"):
        c = AsyncClient(transport=ASGITransport(app=app, client=(ip, 50000)), base_url="http://test")
        clients.append(c)
        return c

    yield _make
    app.dependency_overrides.clear()


@pytest.fixture
def settings(monkeypatch):
    """Settings object; tweak with monkeypatch.setattr(settings, ...)."""
    from app.core.config import get_settings

    return get_settings()


@pytest.fixture(autouse=True)
def _reset_login_guard():
    from app.core.auth import login_guard

    login_guard._failures.clear()
    yield
    login_guard._failures.clear()


@pytest.fixture(autouse=True)
def _tmp_uploads(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


@pytest.fixture
async def admin(seeded, make_client):
    """Logged-in admin client."""
    client = make_client(ip="192.0.2.99")
    r = await client.post("/api/admin/login", json={"username": "admin", "password": "test-password-123"})
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    yield client
    await client.aclose()


async def tree_id(session, code: str) -> int:
    from sqlalchemy import select

    from app.models import Tree

    return await session.scalar(select(Tree.id).where(Tree.code == code))
