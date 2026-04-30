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
make install           # install deps into active virtualenv
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
  schemas/         # Pydantic models
ingestion/         # one-shot CLI pipeline (fetch → chunk → embed → upsert)
eval/              # offline evaluation (golden_dataset.json + LLM-as-judge)
```

## Known gotchas

**hatchling can't find packages on `pip install -e .`**
Add `[tool.hatch.build.targets.wheel] packages = ["app", "ingestion", "eval"]` to `pyproject.toml`.
Hatchling looks for a directory matching the project name (`learn-rag`) and finds nothing.

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
Two causes: (1) `ivfflat` defaults to `probes=1`, searching only ~1% of vectors. Fixed by setting
`ivfflat.probes = 10` in the asyncpg connection init. (2) FastAPI docs contain MDX directives
(`{* path/to/file.py *}`) that pollute chunk embeddings. Fixed by stripping them in `chunker.py`.
Re-run `make ingest` after any chunker change.

## Architecture rules

- Routers call services only — no DB or LLM calls inside route handlers.
- Services orchestrate core primitives — no SQL or HTTP inside services.
- Core modules are stateless infrastructure — no business logic.
- All LLM calls go through `app/core/llm.py`; all tracing through `app/core/tracing.py`.
