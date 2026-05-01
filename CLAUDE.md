# RAG Q&A Service

RAG-powered Q&A over FastAPI documentation. See `DESIGN.md` for full architecture.

## Stack

* Python 3.12
* FastAPI
* PostgreSQL + pgvector
* sentence-transformers (`all-MiniLM-L6-v2`)
* Anthropic (`claude-sonnet-4-6`)
* LangFuse Cloud
* asyncpg.

## Setup

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY and LANGFUSE_* keys
make install           # install deps + set up pre-commit hooks
make db-up             # start PostgreSQL with pgvector
make ingest            # fetch FastAPI docs → chunk → embed → store (run once)
make dev               # start API at http://localhost:8000
```

## Common commands

```bash
make dev               # start API server with hot-reload
make ingest            # re-run ingestion pipeline (idempotent)
make eval              # run offline LLM-as-judge evaluation
make lint              # ruff check
make lint-fix          # ruff check --fix
make format            # ruff format
make test              # pytest
make db-up             # start DB
make db-down           # stop DB
make db-logs           # tail DB logs
```

## Project layout

```
app/
  api/routes/      # HTTP layer only — no business logic
  services/        # business logic (query_service.py owns the RAG flow)
  core/            # infrastructure primitives (embedder, retriever, llm, tracing)
  db/              # asyncpg pool + schema.sql
  schemas/         # Pydantic models (QueryRequest, QueryResponse, RetrievedChunk)
ingestion/         # one-shot CLI pipeline (fetch → chunk → embed → upsert)
eval/              # offline evaluation (golden_dataset.json + LLM-as-judge)
  results/         # timestamped JSON score files — gitignored
```

## Known gotchas

**hatchling can't find packages on `pip install -e .`**
Add `[tool.hatch.build.targets.wheel] packages = ["app", "ingestion", "eval"]` to `pyproject.toml`.
Hatchling looks for a directory matching the project name (`learn_rag`) and finds nothing.

**`ValueError: unknown type: public.vector` on pool init**
The pgvector pool `init` callback runs `register_vector()` before the schema is applied, so the
`vector` extension doesn't exist yet. Fix: open a plain connection, apply `schema.sql`, close it,
then create the pool. See `ingestion/pipeline.py`.

**LangFuse v4 — `langfuse.decorators` does not exist**
In v4, `observe` and `get_client` moved to the top-level package:
`from langfuse import observe, get_client`. The old `langfuse.decorators` module is gone.

**`@observe` on a class method — `trace_id` is empty**
LangFuse v4's `@observe` doesn't propagate trace context correctly on instance methods.
Decorate a module-level function instead; the class method can delegate to it.

**LangFuse `get_client()` ignores `.env` file**
`pydantic-settings` reads `.env` into the `Settings` object but does not write to `os.environ`.
LangFuse calls `os.getenv()` directly, so it sees nothing. Fix: call `load_dotenv()` at the top
of `app/main.py` before any imports that touch LangFuse.

**`LANGFUSE_HOST` vs `LANGFUSE_BASE_URL`**
LangFuse v4 uses `LANGFUSE_BASE_URL` (not `LANGFUSE_HOST`). Updated in `config.py` and `.env.example`.

**Poor retrieval quality — wrong docs ranking first**
Fixed with hybrid BM25 + cosine vector search fused via Reciprocal Rank Fusion (RRF, k=60).
FTS uses a stopword-stripped AND query (`_fts_query()` in `retriever.py`) — generic words like
"fastapi", "how", "handle" are stripped because they appear in questions but not doc content.
Vector pool = `top_k * 5`, FTS pool = `top_k * 3`; final result is top-k by RRF score.

**MDX code examples missing from chunks**
FastAPI docs use `{* docs_src/path/file.py *}` directives to inline Python examples. These are now
replaced with `<<<FETCH:path>>>` markers during chunking; `pipeline.py` fetches the actual source
files from GitHub and substitutes them as fenced code blocks before embedding. MDX paths start with
`../../` which is stripped to a repo-relative path before fetching. Re-run `make ingest` after any
chunker change.

## Architecture rules

- Routers call services only — no DB or LLM calls inside route handlers.
- Services orchestrate core primitives — no SQL or HTTP inside services.
- Core modules are stateless infrastructure — no business logic.
- All LLM calls go through `app/core/llm.py`; all tracing through `app/core/tracing.py`.

## Pydantic rules

- Always use Pydantic v2 syntax: model_dump(), model_copy(update={...})
- FORBIDDEN: .dict() — this is Pydantic v1, always use .model_dump()
- FORBIDDEN: mutating Pydantic model fields directly (e.g. book.status = x)
- Separate input/output schemas: CreateSchema, UpdateSchema, ResponseSchema

## FastAPI rules

- FORBIDDEN: using fastapi.status module name as query/path parameter names — it causes shadowing
  (e.g. use status_filter instead of status for query params)
- Never hardcode HTTP status codes, always use fastapi.status constants
- Always extract repeated 404 logic into a get_or_404() helper, never duplicate it inline

## Python rules

- FORBIDDEN: from typing import Dict, List, Tuple — use built-in generics instead: dict, list, tuple
- Use Python 3.12+ syntax: dict[str, int], list[Book], X | None instead of Optional[X]
- Avoid shadowing built-ins (count, type, id, list, dict, etc.) in variable names
- Use dict comprehension for stats: {s.value: 0 for s in SomeEnum}

## Concise Docstrings

Write comments following these rules:
- Write brief, to-the-point docstrings- avoid AI-generated verbose explanations
- Module docstrings: Single line describing purpose (e.g., `"""Core authentication functions used across all modules"""`)
- Function docstrings: One-line summary for simple functions, Google-style with Args/Returns only when needed
- Simple helpers: One line is enough (e.g., `"""Extract the first path segment from a URL path."""`)
- Complex functions: Add Args/Returns/Examples only when they add real value, not boilerplate

## General

- All code must be production-ready, not tutorial-level
- Prefer itertools.count() over global state for ID generation
- Prefer uuid.uuid4() for IDs when order does not matter
