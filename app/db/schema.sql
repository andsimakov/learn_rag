CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL   PRIMARY KEY,
    source_url  TEXT        NOT NULL,
    chunk_index INTEGER     NOT NULL,
    heading     TEXT,
    content     TEXT        NOT NULL,
    embedding   vector(384) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Weighted FTS: heading terms rank higher than body terms (A > B).
    content_tsv TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(heading, '')), 'A') ||
        setweight(to_tsvector('english', content), 'B')
    ) STORED,

    UNIQUE (source_url, chunk_index)
);

-- Migration: add content_tsv to existing tables (no-op on fresh installs).
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_tsv TSVECTOR
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(heading, '')), 'A') ||
        setweight(to_tsvector('english', content), 'B')
    ) STORED;

-- GIN index for fast full-text search.
CREATE INDEX IF NOT EXISTS documents_content_tsv_idx ON documents USING GIN (content_tsv);

-- No ivfflat index: exact sequential scan is fast enough at ≤10K vectors and avoids
-- the recall penalty of misconfigured list counts. Add ivfflat (lists ≈ sqrt(n))
-- once the corpus exceeds ~10K chunks.
