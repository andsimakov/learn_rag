import re

import asyncpg
import numpy as np

from app.schemas.query import RetrievedChunk

# Standard RRF constant from the original paper.
_RRF_K = 60

# Words stripped before building the FTS query. Two categories:
# (1) Generic question words that don't appear in documentation content.
# (2) "fastapi" — present in ~60% of chunks, provides no discrimination.
_FTS_STOP = frozenset(
    [
        "how",
        "what",
        "where",
        "when",
        "why",
        "which",
        "can",
        "does",
        "a",
        "an",
        "the",
        "in",
        "with",
        "of",
        "for",
        "to",
        "on",
        "at",
        "and",
        "or",
        "my",
        "do",
        "i",
        "is",
        "are",
        "use",
        "using",
        "used",
        "make",
        "get",
        "set",
        "run",
        "handle",
        "define",
        "create",
        "fastapi",
    ]
)


def _fts_query(question: str) -> str | None:
    """Strip generic question words, return remaining terms joined with AND."""
    words = re.sub(r"[^a-z0-9 ]", "", question.lower()).split()
    terms = [w for w in words if w not in _FTS_STOP and len(w) >= 3]
    return " & ".join(terms) if terms else None


async def search(
    pool: asyncpg.Pool,
    vector: np.ndarray,
    query_text: str,
    top_k: int,
) -> list[RetrievedChunk]:
    """Hybrid BM25 + cosine similarity search fused via Reciprocal Rank Fusion."""
    # Larger vector pool catches semantically-distant but relevant chunks
    # (e.g. "handle errors" → "use HTTPException" at vector rank ~38).
    vec_pool = top_k * 5
    fts_pool = top_k * 3
    fts_q = _fts_query(query_text)

    rows = await pool.fetch(
        """
        WITH vector_ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS rank
            FROM documents
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        ),
        fts_ranked AS (
            SELECT d.id,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank_cd(d.content_tsv, to_tsquery('english', $2)) DESC
                   ) AS rank
            FROM documents d
            WHERE $2::text IS NOT NULL
              AND d.content_tsv @@ to_tsquery('english', $2::text)
            ORDER BY ts_rank_cd(d.content_tsv, to_tsquery('english', $2::text)) DESC
            LIMIT $4
        ),
        combined AS (
            SELECT
                COALESCE(v.id, f.id) AS id,
                COALESCE(1.0 / ($5 + v.rank), 0.0) +
                COALESCE(1.0 / ($5 + f.rank), 0.0) AS rrf_score
            FROM vector_ranked v
            FULL OUTER JOIN fts_ranked f ON v.id = f.id
        )
        SELECT d.content, d.source_url, d.heading, c.rrf_score AS score
        FROM combined c
        JOIN documents d ON c.id = d.id
        ORDER BY c.rrf_score DESC
        LIMIT $6
        """,
        vector,
        fts_q,
        vec_pool,
        fts_pool,
        _RRF_K,
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
