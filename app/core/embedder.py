import asyncio
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import get_settings


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


async def warm_up() -> None:
    """Pre-load the model and assert its output dim matches settings.embedding_dim."""
    model = _load_model()
    settings = get_settings()
    loop = asyncio.get_running_loop()
    probe: np.ndarray = await loop.run_in_executor(None, model.encode, "probe")
    actual = probe.shape[0]
    if actual != settings.embedding_dim:
        raise ValueError(
            f"Model '{settings.embedding_model}' produces {actual}-dim vectors "
            f"but embedding_dim={settings.embedding_dim}. "
            "Update EMBEDDING_DIM in .env or switch to the correct model."
        )


async def embed(text: str) -> np.ndarray:
    """Embed a single string. Runs the CPU-bound encode in a thread pool."""
    loop = asyncio.get_running_loop()
    model = _load_model()
    vector: np.ndarray = await loop.run_in_executor(None, model.encode, text)
    return vector.astype(np.float32)


async def embed_batch(texts: list[str], batch_size: int = 64) -> list[np.ndarray]:
    """Embed multiple strings. Used by the ingestion pipeline."""
    loop = asyncio.get_running_loop()
    model = _load_model()

    def _encode() -> np.ndarray:
        return model.encode(texts, batch_size=batch_size, show_progress_bar=True)

    vectors: np.ndarray = await loop.run_in_executor(None, _encode)
    return [v.astype(np.float32) for v in vectors]
