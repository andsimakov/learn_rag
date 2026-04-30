# learn-rag

A RAG service that answers questions about FastAPI by searching its own documentation.
Intentionally built without LangChain — direct control over chunking, retrieval, and prompt construction.

## What it does

1. Fetches FastAPI docs from GitHub, chunks them by section, embeds with `sentence-transformers`, stores in PostgreSQL via `pgvector`.
2. On a query: embeds the question, finds the closest chunks, passes them as context to Claude, returns the answer with source references.
3. Every query is traced in LangFuse — token usage, retrieval scores, latency.

## Stack

- **API** — FastAPI + asyncpg (no ORM)
- **Vector search** — PostgreSQL + pgvector (`all-MiniLM-L6-v2`, 384 dims)
- **LLM** — Anthropic (`claude-sonnet-4-6`)
- **Observability** — LangFuse Cloud
- **Local infra** — Docker Compose (DB only)

## Setup

```bash
cp .env.example .env      # add ANTHROPIC_API_KEY and LANGFUSE_* keys
make install              # install dependencies
make db-up                # start PostgreSQL with pgvector
make ingest               # fetch docs, embed, store — run once
make dev                  # API at http://localhost:8000
```

Query example:

```bash
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I declare path parameters?"}' | python -m json.tool
```

## Evaluation

```bash
make eval
```

Runs 15 questions from `eval/golden_dataset.json` through the pipeline and scores each answer with an LLM judge on faithfulness and relevance (1–5).

## Project structure

```
app/
  api/routes/    routers — HTTP only, call services and return
  services/      business logic — owns the RAG flow
  core/          infrastructure — embedder, retriever, LLM client, tracing
  db/            asyncpg pool + schema
  schemas/       Pydantic models
ingestion/       one-shot pipeline: fetch → chunk → embed → upsert
eval/            offline evaluation: golden dataset + LLM-as-judge
```

See `DESIGN.md` for architecture decisions and data flow details.
