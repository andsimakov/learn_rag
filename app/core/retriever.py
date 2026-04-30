import asyncpg
import numpy as np

from app.schemas.query import RetrievedChunk


async def search(
    pool: asyncpg.Pool,
    vector: np.ndarray,
    top_k: int,
) -> list[RetrievedChunk]:
    """Return the top_k most similar chunks using cosine similarity."""
    rows = await pool.fetch(
        """
        SELECT
            content,
            source_url,
            heading,
            1 - (embedding <=> $1::vector) AS score
        FROM documents
        ORDER BY embedding <=> $1::vector
        LIMIT $2
        """,
        vector,
        top_k,
    )
    return [
        RetrievedChunk(
            content=row["content"],
            source_url=row["source_url"],
            heading=row["heading"],
            score=float(row["score"]),
        )
        for row in rows
    ]
