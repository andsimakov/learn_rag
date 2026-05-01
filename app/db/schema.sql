CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL   PRIMARY KEY,
    source_url  TEXT        NOT NULL,
    chunk_index INTEGER     NOT NULL,
    heading     TEXT,
    content     TEXT        NOT NULL,
    embedding   vector(384) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (source_url, chunk_index)
);

-- No ivfflat index: exact sequential scan is fast enough at ≤10K vectors and avoids
-- the recall penalty of misconfigured list counts. Add ivfflat (lists ≈ sqrt(n))
-- once the corpus exceeds ~10K chunks.
