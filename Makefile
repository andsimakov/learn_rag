.DEFAULT_GOAL := help

# ── Environment ───────────────────────────────────────────────────────────────

.PHONY: install
install:  ## Install all dependencies (including dev) and set up pre-commit hooks
	uv pip install -e ".[dev]"
	pre-commit install

# ── Database ──────────────────────────────────────────────────────────────────

.PHONY: db-up
db-up:  ## Start PostgreSQL with pgvector
	docker compose up -d db

.PHONY: db-down
db-down:  ## Stop and remove the database container
	docker compose down

.PHONY: db-logs
db-logs:  ## Tail database logs
	docker compose logs -f db

# ── Ingestion ─────────────────────────────────────────────────────────────────

.PHONY: ingest
ingest:  ## Fetch FastAPI docs, chunk, embed, and store in pgvector
	python -m ingestion.pipeline

# ── App ───────────────────────────────────────────────────────────────────────

.PHONY: dev
dev:  ## Start the API server with hot-reload
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Evaluation ────────────────────────────────────────────────────────────────

.PHONY: eval
eval:  ## Run the offline LLM-as-judge evaluation
	python -m eval.run_eval

# ── Code quality ──────────────────────────────────────────────────────────────

.PHONY: lint
lint:  ## Check code style and imports
	ruff check .

.PHONY: lint-fix
lint-fix:  ## Auto-fix lint issues
	ruff check . --fix

.PHONY: format
format:  ## Format all Python files
	ruff format .

.PHONY: check
check: lint format  ## Run lint + format (CI-style, no auto-fix)

# ── Tests ─────────────────────────────────────────────────────────────────────

.PHONY: test
test:  ## Run the test suite
	pytest

# ── Frontend ──────────────────────────────────────────────────────────────────

.PHONY: client-install
client-install:  ## Install frontend dependencies
	cd client && npm install

.PHONY: client
client:  ## Start the frontend dev server on http://localhost:3000
	cd client && npm run dev

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
