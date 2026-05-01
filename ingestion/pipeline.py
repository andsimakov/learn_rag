"""
Ingestion pipeline — run once to populate pgvector with FastAPI docs.

    python -m ingestion.pipeline
"""

import asyncio
from pathlib import Path

import asyncpg
import numpy as np
from pgvector.asyncpg import register_vector

from app.config import get_settings
from app.core.embedder import embed_batch
from ingestion.chunker import Chunk, chunk_document, extract_fetch_paths, substitute_code
from ingestion.fetcher import fetch_code_files, fetch_fastapi_docs

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

    print("Connecting to database…")
    # Apply schema first via a plain connection — the vector extension must exist
    # before register_vector() can be used in the pool init callback.
    conn = await asyncpg.connect(dsn=settings.database_url)
    await _apply_schema(conn)
    await conn.close()
    print("Schema applied.")

    pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=5,
        init=lambda conn: register_vector(conn),
    )

    try:
        print("Fetching FastAPI docs from GitHub…")
        docs = await fetch_fastapi_docs()
        print(f"Downloaded {len(docs)} files.")

        print("Chunking…")
        all_chunks: list[Chunk] = []
        for doc in docs:
            all_chunks.extend(chunk_document(doc.path, doc.content))
        print(f"Created {len(all_chunks)} chunks.")

        print("Fetching code examples…")
        code_paths = extract_fetch_paths(all_chunks)
        print(f"  {len(code_paths)} unique Python files referenced in docs")
        code_map = await fetch_code_files(code_paths)
        print(f"  {len(code_map)} fetched successfully")
        all_chunks = substitute_code(all_chunks, code_map)
        print(f"  {len(all_chunks)} chunks after code substitution")

        print("Embedding…")
        texts = [c.content for c in all_chunks]
        vectors = await embed_batch(texts)
        print(f"Embedded {len(vectors)} vectors.")

        print("Upserting to database…")
        for i in range(0, len(all_chunks), _UPSERT_BATCH):
            batch_chunks = all_chunks[i : i + _UPSERT_BATCH]
            batch_vectors = vectors[i : i + _UPSERT_BATCH]
            await _upsert_batch(pool, batch_chunks, batch_vectors)
            done = min(i + _UPSERT_BATCH, len(all_chunks))
            print(f"  {done}/{len(all_chunks)}")
    finally:
        await pool.close()

    print("Pipeline complete.")


if __name__ == "__main__":
    asyncio.run(run())
