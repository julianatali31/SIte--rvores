from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings


def build_engine(settings: Settings) -> AsyncEngine:
    if not settings.serverless:
        return create_async_engine(settings.database_url, pool_pre_ping=True)
    # Serverless + Neon pooler (PgBouncer, transaction mode): no client-side pool and
    # no reused prepared statements, otherwise asyncpg collides across connections.
    url = make_url(settings.database_url).update_query_dict({"prepared_statement_cache_size": "0"})
    return create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        },
    )


engine = build_engine(get_settings())
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
