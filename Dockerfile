FROM python:3.12-slim

RUN adduser --system --no-create-home --uid 1001 appuser

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache -e .

COPY --chown=appuser . .

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
