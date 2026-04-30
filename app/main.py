from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env into os.environ before anything reads from it.
# pydantic-settings populates the Settings object from .env but does NOT write
# back to os.environ, so libraries like LangFuse that call os.getenv() directly
# would find nothing without this call.
load_dotenv()

from fastapi import FastAPI  # noqa: E402

from app.api.routes import health, query  # noqa: E402
from app.core.embedder import warm_up  # noqa: E402
from app.db.connection import close_pool, create_pool  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await create_pool()
    warm_up()
    yield
    await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title="FastAPI RAG Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(query.router, prefix="/api/v1", tags=["query"])
    return app


app = create_app()
