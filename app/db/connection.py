import asyncpg
from pgvector.asyncpg import register_vector

from app.config import get_settings

_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        init=_init_connection,
    )
    return _pool


async def _init_connection(conn: asyncpg.Connection) -> None:
    await register_vector(conn)
    # Probe more ivfflat clusters per query for better recall.
    # Default probes=1 searches ~1% of vectors — too lossy for a small corpus.
    await conn.execute("SET ivfflat.probes = 10")


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized — call create_pool() first.")
    return _pool
