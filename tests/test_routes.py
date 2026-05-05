from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.query import router
from app.schemas.query import QueryResponse, RetrievedChunk

# Minimal app — no lifespan, no DB pool, no embedder warm-up.
_app = FastAPI()
_app.include_router(router)
client = TestClient(_app)


def _fake_response() -> QueryResponse:
    return QueryResponse(
        answer="Test answer.",
        sources=[RetrievedChunk(content="doc", source_url="https://x", heading=None, score=0.9)],
        trace_id="trace-123",
    )


def test_query_returns_200(mocker):
    mocker.patch("app.api.routes.query.answer", return_value=_fake_response())
    resp = client.post("/query", json={"question": "What is FastAPI?", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Test answer."
    assert data["trace_id"] == "trace-123"
    assert len(data["sources"]) == 1


def test_query_returns_500_on_exception(mocker):
    mocker.patch("app.api.routes.query.answer", side_effect=RuntimeError("boom"))
    resp = client.post("/query", json={"question": "What is FastAPI?", "top_k": 5})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal server error"


def test_query_returns_422_for_empty_question():
    resp = client.post("/query", json={"question": "", "top_k": 5})
    assert resp.status_code == 422
