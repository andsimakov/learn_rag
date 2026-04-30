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

-- ivfflat: approximate nearest-neighbour; lists=100 suits collections up to ~1M vectors.
-- FastAPI docs produce ~2K-4K chunks, so this is more than sufficient.
CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
