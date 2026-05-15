"""
Ingestion pipeline — run once to populate pgvector with FastAPI docs.

    python -m ingestion.pipeline
"""

import asyncio
import logging
from pathlib import Path

import asyncpg
import numpy as np
from pgvector.asyncpg import register_vector

from app.config import get_settings
from app.core.embedder import embed_batch
from app.core.logging import configure_logging
from ingestion.chunker import Chunk, chunk_document, extract_fetch_paths, substitute_code
from ingestion.fetcher import fetch_code_files, fetch_fastapi_docs

configure_logging()

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent / "app" / "db" / "schema.sql"
_UPSERT_BATCH = 100


async def _apply_schema(conn: asyncpg.Connection) -> None:
    await conn.execute(_SCHEMA_PATH.read_text())


async def _upsert_batch(
    pool: asyncpg.Pool,
    chunks: list[Chunk],
    vectors: list[np.ndarray],
) -> None:
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO documents (source_url, chunk_index, heading, content, embedding)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (source_url, chunk_index) DO UPDATE SET
                heading   = EXCLUDED.heading,
                content   = EXCLUDED.content,
                embedding = EXCLUDED.embedding
            """,
            [(c.source_url, c.chunk_index, c.heading, c.content, v) for c, v in zip(chunks, vectors)],
        )


async def run() -> None:
    settings = get_settings()

    logger.info("connecting to database")
    conn = await asyncpg.connect(dsn=settings.database_url)
    try:
        await _apply_schema(conn)
    finally:
        await conn.close()
    logger.info("schema applied")

    pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=5,
        init=register_vector,
    )

    try:
        logger.info("fetching fastapi docs from github")
        docs = await fetch_fastapi_docs()
        logger.info("docs downloaded", extra={"count": len(docs)})

        logger.info("chunking docs")
        all_chunks: list[Chunk] = []
        for doc in docs:
            all_chunks.extend(chunk_document(doc.path, doc.content))
        logger.info("chunks created", extra={"count": len(all_chunks)})

        logger.info("fetching code examples")
        code_paths = extract_fetch_paths(all_chunks)
        logger.info("code files referenced", extra={"unique_files": len(code_paths)})
        code_map = await fetch_code_files(code_paths)
        logger.info("code files fetched", extra={"fetched": len(code_map)})
        all_chunks = substitute_code(all_chunks, code_map)
        logger.info("chunks after code substitution", extra={"count": len(all_chunks)})

        logger.info("embedding chunks")
        texts = [c.content for c in all_chunks]
        vectors = await embed_batch(texts)
        logger.info("vectors embedded", extra={"count": len(vectors)})

        logger.info("upserting to database")
        for i in range(0, len(all_chunks), _UPSERT_BATCH):
            batch_chunks = all_chunks[i : i + _UPSERT_BATCH]
            batch_vectors = vectors[i : i + _UPSERT_BATCH]
            await _upsert_batch(pool, batch_chunks, batch_vectors)
            done = min(i + _UPSERT_BATCH, len(all_chunks))
            logger.info("upsert progress", extra={"done": done, "total": len(all_chunks)})
    finally:
        await pool.close()

    logger.info("pipeline complete")


if __name__ == "__main__":
    asyncio.run(run())
