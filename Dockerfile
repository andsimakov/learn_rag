FROM python:3.12-slim

RUN adduser --system --no-create-home --uid 1001 appuser \
    && mkdir -p /cache && chown appuser /cache

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install CPU-only torch before the main install — without this, PyPI serves
# the CUDA variant (adds ~4 GB of GPU libraries we don't need).
# pyproject.toml is copied first so this layer is only invalidated when
# dependencies change, not on every source file edit.
COPY pyproject.toml .
RUN uv pip install --system --no-cache \
    torch --index-url https://download.pytorch.org/whl/cpu
RUN uv pip install --system --no-cache .

COPY --chown=appuser . .

USER appuser

ENV HF_HOME=/cache

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
