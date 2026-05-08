"""Tests for stream_answer in app/services/query_service.py."""

from app.schemas.query import QueryRequest, RetrievedChunk
from app.services.query_service import stream_answer


def _make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        content="FastAPI is a modern web framework.",
        source_url="https://fastapi.tiangolo.com/",
        heading="Intro",
        score=0.95,
    )


def _make_request() -> QueryRequest:
    return QueryRequest(question="What is FastAPI?", top_k=5)


async def _token_generator(*tokens: str):
    for token in tokens:
        yield token


async def test_stream_answer_happy_path(mocker):
    mocker.patch("app.core.retriever.get_pool", return_value=mocker.MagicMock())
    mocker.patch(
        "app.services.query_service.embedder.embed",
        new_callable=mocker.AsyncMock,
        return_value=[0.1] * 384,
    )
    mocker.patch(
        "app.services.query_service.retriever.search",
        new_callable=mocker.AsyncMock,
        return_value=[_make_chunk()],
    )
    mocker.patch(
        "app.services.query_service.stream_generate",
        return_value=_token_generator("Hello", " world"),
    )

    mock_trace = mocker.MagicMock()
    mock_trace.id = "trace-abc"
    mock_lf = mocker.MagicMock()
    mock_lf.trace.return_value = mock_trace
    mocker.patch("app.services.query_service.get_client", return_value=mock_lf)

    events = [event async for event in stream_answer(_make_request())]

    sources_events = [e for e in events if e["type"] == "sources"]
    token_events = [e for e in events if e["type"] == "token"]
    done_events = [e for e in events if e["type"] == "done"]

    assert len(sources_events) == 1
    assert len(sources_events[0]["sources"]) == 1

    assert len(token_events) == 2
    assert token_events[0]["text"] == "Hello"
    assert token_events[1]["text"] == " world"

    assert len(done_events) == 1
    assert done_events[0]["trace_id"] == "trace-abc"


async def test_stream_answer_langfuse_failure_yields_empty_trace_id(mocker):
    mocker.patch("app.core.retriever.get_pool", return_value=mocker.MagicMock())
    mocker.patch(
        "app.services.query_service.embedder.embed",
        new_callable=mocker.AsyncMock,
        return_value=[0.1] * 384,
    )
    mocker.patch(
        "app.services.query_service.retriever.search",
        new_callable=mocker.AsyncMock,
        return_value=[_make_chunk()],
    )
    mocker.patch(
        "app.services.query_service.stream_generate",
        return_value=_token_generator("Hello", " world"),
    )
    mocker.patch(
        "app.services.query_service.get_client",
        side_effect=RuntimeError("langfuse down"),
    )

    events = [event async for event in stream_answer(_make_request())]

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["trace_id"] == ""


async def test_stream_answer_no_chunks_yields_fallback(mocker):
    mocker.patch("app.core.retriever.get_pool", return_value=mocker.MagicMock())
    mocker.patch(
        "app.services.query_service.embedder.embed",
        new_callable=mocker.AsyncMock,
        return_value=[0.1] * 384,
    )
    mocker.patch(
        "app.services.query_service.retriever.search",
        new_callable=mocker.AsyncMock,
        return_value=[],
    )

    events = [event async for event in stream_answer(_make_request())]

    sources_events = [e for e in events if e["type"] == "sources"]
    token_events = [e for e in events if e["type"] == "token"]
    done_events = [e for e in events if e["type"] == "done"]

    assert len(sources_events) == 1
    assert sources_events[0]["sources"] == []

    assert len(token_events) == 1
    assert token_events[0]["text"] == "No relevant documentation found."

    assert len(done_events) == 1
    assert done_events[0]["trace_id"] == ""
