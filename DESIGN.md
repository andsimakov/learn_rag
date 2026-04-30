# RAG Q&A Service — Design Document

## Overview

A production-quality RAG (Retrieval-Augmented Generation) service that answers questions about
FastAPI by retrieving relevant documentation chunks and generating answers via Claude. Built as a
portfolio project demonstrating real LLM engineering practices.

**Stack:** Python 3.12, FastAPI, PostgreSQL + pgvector, sentence-transformers, Anthropic, LangFuse

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        INGESTION PIPELINE                       │
│   (one-shot CLI, run once to populate the vector store)         │
│                                                                 │
│  GitHub API ──► Fetcher ──► Chunker ──► Embedder ──► Repository │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         QUERY FLOW                              │
│                                                                 │
│  HTTP Request                                                   │
│      │                                                          │
│      ▼                                                          │
│  [Router] ───────────────────────────────────────────────────►  │
│      │         parse + validate (Pydantic)                      │
│      ▼                                                          │
│  [QueryService]                                                 │
│      │  1. embed question        ──► [Embedder]                 │
│      │  2. semantic search       ──► [Retriever → pgvector]     │
│      │  3. build prompt + call   ──► [LLMClient → Anthropic]    │
│      │  4. trace everything      ──► [LangFuse Cloud]           │
│      ▼                                                          │
│  [Router] ──► HTTP Response (answer + source chunks)            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     OFFLINE EVALUATION                          │
│                                                                 │
│  golden_dataset.json ──► RAG pipeline ──► LLM-as-judge          │
│                                               │                 │
│                                               ▼                 │
│                                       score report (stdout)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layered Architecture

The app follows a strict three-layer separation. Each layer has one responsibility and depends only on layers below it.

```
┌────────────────────────────────────────────────────────┐
│  API Layer  (app/api/)                                 │
│  HTTP concerns only: routing, request/response,        │
│  status codes, dependency injection via FastAPI.       │
│  Routers call services — nothing else.                 │
├────────────────────────────────────────────────────────┤
│  Service Layer  (app/services/)                        │
│  Business logic: orchestrate operations, make          │
│  decisions, compose core primitives into workflows.    │
│  No HTTP, no SQL — pure Python.                        │
├────────────────────────────────────────────────────────┤
│  Core / Infrastructure Layer  (app/core/)              │
│  Low-level clients and adapters: embedder, retriever,  │
│  LLM client, LangFuse tracer. Answer "how to do X",    │
│  not "when or why". No business logic here.            │
├────────────────────────────────────────────────────────┤
│  DB Layer  (app/db/)                                   │
│  asyncpg connection pool + raw SQL queries.            │
│  No ORM — keeps it transparent and fast.               │
└────────────────────────────────────────────────────────┘
```

### Why this matters

| Without separation | With separation |
|---|---|
| Router fetches from DB, calls LLM, formats response | Router calls `service.answer(question)` and returns |
| Can't unit-test business logic without HTTP | Services are plain async functions — trivial to test |
| Swapping Anthropic for another LLM touches routers | Only `LLMClient` changes |
| Ingestion pipeline duplicates embedding code | Both pipeline and service use the same `Embedder` |

---

## Project Structure

```
learn_rag/
│
├── pyproject.toml              # dependencies + tool config (ruff)
├── docker-compose.yml          # PostgreSQL with pgvector
├── Dockerfile                  # app image
├── .env.example                # required env vars documented
│
├── app/                        # FastAPI service
│   ├── main.py                 # app factory, lifespan, router registration
│   ├── config.py               # pydantic-settings: all env vars in one place
│   │
│   ├── api/
│   │   ├── deps.py             # FastAPI Depends() providers
│   │   └── routes/
│   │       ├── query.py        # POST /query  (router only)
│   │       └── health.py       # GET  /health
│   │
│   ├── services/
│   │   └── query_service.py    # orchestrates embed → retrieve → generate → trace
│   │
│   ├── core/
│   │   ├── embedder.py         # sentence-transformers wrapper (async-safe)
│   │   ├── retriever.py        # pgvector ANN search queries
│   │   ├── llm.py              # Anthropic async client + LangFuse generation tracing
│   │   └── tracing.py          # LangFuse v4 usage reference (decorator pattern)
│   │
│   ├── db/
│   │   ├── connection.py       # asyncpg pool init + teardown
│   │   └── schema.sql          # DDL: pgvector extension + documents table
│   │
│   └── schemas/
│       └── query.py            # Pydantic models: QueryRequest, QueryResponse,
│                               #   RetrievedChunk, EvalScore
│
├── ingestion/
│   ├── fetcher.py              # GitHub API → raw markdown files
│   ├── chunker.py              # section-aware markdown splitter
│   └── pipeline.py             # CLI entrypoint: fetch → chunk → embed → upsert
│
└── eval/
    ├── golden_dataset.json     # 15 hand-crafted Q&A pairs
    ├── judge.py                # LLM-as-judge: faithfulness + relevance scores
    └── run_eval.py             # CLI: runs eval loop, prints score table
```

---

## Component Responsibilities

### `app/main.py`
- Calls `load_dotenv()` before any imports — required so LangFuse can read `LANGFUSE_*` from `os.environ` (pydantic-settings does not write back to the environment)
- Creates the FastAPI app instance
- Registers the lifespan context manager (DB pool init/teardown, model load)
- Mounts all routers with version prefix (`/api/v1`)

### `app/config.py`
- Single `Settings` class via `pydantic-settings`
- Reads from environment / `.env` file
- Accessed as a singleton via `get_settings()` (lru_cache)
- All secrets and tunable knobs live here

### `app/api/deps.py`
- FastAPI `Depends()` providers
- Provides `QueryService`, `Embedder`, DB pool to routes
- Keeps routes free of construction logic

### `app/api/routes/query.py`
- Accepts `POST /api/v1/query` with `QueryRequest`
- Calls `QueryService.answer()`
- Returns `QueryResponse`
- Handles HTTP-level errors (422, 500)

### `app/services/query_service.py`
- `QueryService.answer()` delegates to the module-level `_answer()` function
- `@observe` must wrap a module-level function — it does not propagate trace context correctly on class instance methods in LangFuse v4
- `_answer()` owns the RAG prompt template and assembles the full flow: embed → retrieve → generate
- LangFuse tracing via `@observe(name="rag_query")` on `_answer()` and `get_client()` for I/O metadata

### `app/core/embedder.py`
- Wraps `sentence-transformers` `all-MiniLM-L6-v2`
- `embed(text: str) → list[float]` — single text
- `embed_batch(texts: list[str]) → list[list[float]]` — used by ingestion
- Model is loaded once at startup, reused across requests

### `app/core/retriever.py`
- `search(pool, vector, top_k) → list[RetrievedChunk]`
- Runs pgvector cosine similarity query
- Returns chunks sorted by relevance score
- No embedding logic — receives a vector, returns chunks

### `app/core/llm.py`
- Thin async wrapper around `anthropic.AsyncAnthropic`
- `generate(question, chunks, system_prompt) → str`
- Decorated with `@observe(as_type="generation")` — LangFuse v4 records model, token counts, and cost automatically
- Uses `get_client().update_current_generation()` to attach metadata to the active span
- One place to change model or max_tokens

### `app/db/connection.py`
- `create_pool()` / `close_pool()` — called in lifespan
- `get_pool()` — returns the module-level pool instance
- Uses `asyncpg` + pgvector codec registration
- Sets `ivfflat.probes = 10` per connection — the default of 1 searches only ~1% of vectors, causing poor recall on small corpora

### `ingestion/pipeline.py`
- CLI script: `python -m ingestion.pipeline`
- Calls `Fetcher → Chunker → Embedder.embed_batch → upsert into DB`
- Idempotent: upserts on `(source_url, chunk_index)` unique key
- Progress logging per batch

### `eval/judge.py`
- `judge(question, context, answer, reference) → EvalScore`
- Sends a structured prompt to Claude asking for JSON with:
  - `faithfulness` (1–5): every claim grounded in context?
  - `relevance` (1–5): answer addresses the question?
  - `reasoning`: one-sentence explanation
- Returns `EvalScore` Pydantic model

### `eval/run_eval.py`
- CLI: `python -m eval.run_eval`
- Loads `golden_dataset.json`
- For each entry: run RAG pipeline → judge → collect score
- Prints a table with per-question scores + aggregate averages

---

## Data Model

### `documents` table (pgvector)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id           BIGSERIAL PRIMARY KEY,
    source_url   TEXT        NOT NULL,  -- e.g. "docs/en/tutorial/first-steps.md"
    chunk_index  INTEGER     NOT NULL,  -- position within source file
    heading      TEXT,                  -- nearest ## heading, for display
    content      TEXT        NOT NULL,  -- raw markdown text of the chunk
    embedding    vector(384) NOT NULL,  -- all-MiniLM-L6-v2 output
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (source_url, chunk_index)
);

CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

**Why `ivfflat`?** Approximate nearest-neighbour index built into pgvector. `lists = 100` is
appropriate for collections up to ~1M vectors; FastAPI docs produce ~2K–4K chunks so this is
generous. Alternative `hnsw` offers better recall but higher memory — not needed at this scale.

### Pydantic Schemas

```python
# Request
class QueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)

# Internal transfer object (not exposed)
class RetrievedChunk(BaseModel):
    content: str
    source_url: str
    heading: str | None
    score: float          # cosine similarity 0–1

# Response
class QueryResponse(BaseModel):
    answer: str
    sources: list[RetrievedChunk]
    trace_id: str         # LangFuse trace ID for debugging

# Eval
class EvalScore(BaseModel):
    faithfulness: int     # 1–5
    relevance: int        # 1–5
    reasoning: str
```

---

## Query Flow (Detailed)

```
POST /api/v1/query
  {"question": "How do I declare path parameters?", "top_k": 5}

1. Router validates request (Pydantic) → calls QueryService.answer()

2. _answer() — decorated with @observe(name="rag_query"):
   a. Embedder: embed(question) → vector[384]
   b. Retriever: search(vector, top_k=5) → chunks
   c. Build prompt:
        system: "Answer using ONLY the provided context."
        user:   "<context>\n{chunks}\n</context>\n\nQuestion: {question}"
   d. generate(question, chunks, system_prompt) → answer_text  [LangFuse generation]
   e. get_client().set_current_trace_io(output=answer_text)

3. Router returns:
   {
     "answer": "Path parameters are declared using ...",
     "sources": [{"content": "...", "source_url": "...", "score": 0.91}, ...],
     "trace_id": "abc123"
   }
```

---

## Ingestion Flow (Detailed)

```
python -m ingestion.pipeline

1. Fetcher:
   - Hit GitHub API: GET /repos/fastapi/fastapi/git/trees/master?recursive=1
   - Filter files matching docs/en/**/*.md
   - Download each file via raw.githubusercontent.com
   - Yield (source_path, markdown_content)

2. Chunker (per file):
   - Strip MDX include directives (`{* path/to/file.py *}`) and heading anchors (`{ #slug }`) — these are FastAPI docs build artifacts that pollute embeddings
   - Split on ## and ### headings
   - Each chunk = heading text + content below it
   - If chunk > 800 chars: split further with 100-char overlap
   - Yield (source_path, chunk_index, heading, content)

3. Embedder:
   - embed_batch(chunk_texts, batch_size=64) → vectors
   - sentence-transformers handles batching internally

4. Repository:
   - asyncpg executemany: INSERT ... ON CONFLICT (source_url, chunk_index) DO UPDATE
   - Idempotent — safe to re-run
```

---

## LangFuse Tracing Structure

Every query produces one trace with a nested generation:

```
trace: rag_query              (@observe on _answer() — sets input/output via get_client())
  └── generation: llm_call    (@observe(as_type="generation") on generate() — model, tokens, cost)
```

Tracing uses the LangFuse v4 decorator API (`from langfuse import observe, get_client`).
The `@observe` decorator creates the trace context; `get_client()` attaches metadata to the active span.

---

## Evaluation Design

### Golden Dataset Format

```json
[
  {
    "question": "How do I declare an optional query parameter?",
    "reference_answer": "Use Optional[str] = None or str | None = None as the default."
  }
]
```

### Judge Prompt Structure

```
You are evaluating a RAG system answer.

Question: {question}
Retrieved context: {context}
Generated answer: {answer}
Reference answer: {reference_answer}

Score on two dimensions (1–5):
- faithfulness: is every claim in the answer supported by the context?
  (5 = fully grounded, 1 = contradicts or ignores context)
- relevance: does the answer address the question?
  (5 = complete and direct, 1 = misses the point)

Respond with JSON only: {"faithfulness": N, "relevance": N, "reasoning": "..."}
```

### Score Report

```
Question                                    Faithfulness  Relevance
─────────────────────────────────────────────────────────────────
How do I declare path parameters?                5            5
How do I add request body validation?            4            5
...
─────────────────────────────────────────────────────────────────
Average                                          4.6          4.8
```

---

## Dependencies

See `pyproject.toml` for the current pinned versions. Key entries:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "asyncpg>=0.29.0",
    "pgvector>=0.3.6",
    "sentence-transformers>=3.3.0",
    "anthropic>=0.40.0",
    "langfuse>=2.50.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "numpy>=1.26.0",
]

[tool.ruff]
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "W292"]
```

---

## Environment Variables

```bash
# .env.example

# Database
DATABASE_URL=postgresql://rag_user:rag_password@localhost:5432/rag_db

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6

# LangFuse Cloud
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# App
LOG_LEVEL=INFO
TOP_K_DEFAULT=5
```

