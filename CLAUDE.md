# RAG Q&A Service

RAG-powered Q&A over FastAPI documentation. See `DESIGN.md` for full architecture.

## Stack

* Python 3.12
* FastAPI
* PostgreSQL + pgvector
* sentence-transformers (`all-MiniLM-L6-v2`)
* Anthropic (`claude-sonnet-4-6`)
* LangFuse Cloud
* asyncpg
* React 19 + Next.js 16 + Tailwind v4 (client/)

## Setup

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY and LANGFUSE_* keys
make install           # install deps + set up pre-commit hooks
make db-up             # start PostgreSQL with pgvector
make ingest            # fetch FastAPI docs → chunk → embed → store (run once)
make dev               # start API at http://localhost:8000
make client-install    # install frontend npm dependencies (first time only)
make client            # start frontend at http://localhost:3000
```

## Common commands

```bash
make dev               # start API server with hot-reload
make client            # start frontend dev server (http://localhost:3000)
make client-install    # install frontend npm dependencies
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

### Docker (full stack)

```bash
docker compose --profile app up --build   # build and start DB + API + client
docker compose --profile app up           # start without rebuilding
docker compose down                       # stop (preserves volumes)
docker compose down -v                    # stop and delete volumes (data loss!)
```

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000` and is baked into the
client bundle at build time. Override before building if deploying elsewhere:
`NEXT_PUBLIC_API_URL=https://api.example.com docker compose --profile app up --build`

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
client/            # Next.js 16 chat frontend
  src/
    app/           # Next.js App Router (page.tsx, layout.tsx)
    components/    # ChatInput, MessageList, MessageItem, SourcesList
    lib/api.ts     # fetch-based SSE client (async generator)
    types/api.ts   # TypeScript interfaces matching backend schemas
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
In v4, `observe` and `get_client` moved to the top-level package. The old `langfuse.decorators`
module is gone. Import via the re-export shim: `from app.core.tracing import observe, get_client`.

**`@observe` on a class method — `trace_id` is empty**
LangFuse v4's `@observe` doesn't propagate trace context correctly on instance methods.
Decorate a module-level function instead. `QueryService` was removed entirely once we confirmed
the wrapper class added nothing but indirection — `query_service.py` now exposes `answer()` directly.

**`@observe` works on async generators in v4**
`@observe` can decorate async generator functions in LangFuse v4. Both `answer()` and `stream_answer()`
use `@observe`. Input/output are set explicitly via `lf.update_current_span(input=..., output=...)` —
`set_current_trace_io()` and `update_current_observation()` do not exist in v4. Wrap all `get_client()`
calls in try/except so tracing failures degrade gracefully without breaking the stream.

**LangFuse `get_client()` ignores `.env` file**
`pydantic-settings` reads `.env` into the `Settings` object but does not write to `os.environ`.
LangFuse calls `os.getenv()` directly, so it sees nothing. Fix: call `load_dotenv()` at the top
of `app/main.py` before any imports that touch LangFuse.

**`LANGFUSE_HOST` vs `LANGFUSE_BASE_URL`**
LangFuse v4 uses `LANGFUSE_BASE_URL` (not `LANGFUSE_HOST`). Updated in `config.py` and `.env.example`.

**LangFuse 401 errors in tests**
Tests stub `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` as `"test"`, which satisfies `Settings()`
validation but causes the client to flush spans against the real API and receive 401. Fix: set
`LANGFUSE_TRACING_ENABLED=false` in `tests/conftest.py` — LangFuse v4 checks this env var at init
time and disables all network activity before any connection is attempted.

**Docker API container — `PermissionError: /nonexistent` on startup**
The non-root `appuser` has no home directory, so HuggingFace defaults its cache to `/nonexistent`.
Fix: create `/cache` at image build time and set `HF_HOME=/cache`. The model (~90 MB) is downloaded
on first container start and persists in the `hf_cache` named Docker volume across rebuilds.

**Docker API image — 5 GB with GPU PyTorch**
`sentence-transformers` pulls full CUDA PyTorch by default. Fix: install CPU-only torch first via
`--index-url https://download.pytorch.org/whl/cpu` before the main `uv pip install .`. Reduces
image from ~5 GB to ~1.1 GB. `pyproject.toml` must be copied before pip install layers so that
source-file changes don't invalidate the torch cache layer.

**Poor retrieval quality — wrong docs ranking first**
Fixed with hybrid BM25 + cosine vector search fused via Reciprocal Rank Fusion (RRF, k=60).
Key tuning decisions: (1) FTS uses AND semantics with a stopword list — OR semantics matched
"fastapi" in ~60% of chunks, flooding results; words like "handle" appear in questions but not
in doc content so they're stripped. (2) Vector pool = `top_k * 5` because semantically distant
but correct chunks (e.g. "use HTTPException" for "handle errors") ranked outside top-k. (3) No
`ivfflat` index — at ~1K chunks exact scan is faster and more accurate than ANN approximation.

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
