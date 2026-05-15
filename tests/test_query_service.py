"""Tests for answer() and stream_answer() in app/services/query_service.py."""

from app.schemas.query import QueryRequest, QueryResponse, RetrievedChunk
from app.services.query_service import answer, stream_answer


def _make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        content="FastAPI is a modern web framework.",
        source_url="https://fastapi.tiangolo.com/",
        heading="Intro",
        score=0.95,
    )


def _make_request() -> QueryRequest:
    return QueryRequest(question="What is FastAPI?", top_k=5)


def _mock_lf(mocker, trace_id: str = "trace-xyz"):
    mock_lf = mocker.MagicMock()
    mock_lf.get_current_trace_id.return_value = trace_id
    mocker.patch("app.services.query_service.get_client", return_value=mock_lf)
    return mock_lf


async def test_answer_happy_path(mocker):
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
        "app.services.query_service.generate",
        new_callable=mocker.AsyncMock,
        return_value="FastAPI is a web framework.",
    )
    mock_lf = _mock_lf(mocker, "trace-xyz")

    result = await answer(_make_request())

    assert isinstance(result, QueryResponse)
    assert result.answer == "FastAPI is a web framework."
    assert result.trace_id == "trace-xyz"
    assert len(result.sources) == 1
    mock_lf.update_current_span.assert_called_once_with(
        input={"question": "What is FastAPI?", "top_k": 5},
        output={"answer": "FastAPI is a web framework."},
    )


async def test_answer_no_chunks_returns_fallback(mocker):
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

    result = await answer(_make_request())

    assert result.answer == "No relevant documentation found."
    assert result.sources == []
    assert result.trace_id == ""


async def _token_generator(*tokens: str):
    for token in tokens:
        yield token


async def test_stream_answer_happy_path(mocker):
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
    mock_lf = _mock_lf(mocker, "trace-abc")

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
    mock_lf.update_current_span.assert_called_once_with(
        input={"question": "What is FastAPI?", "top_k": 5},
        output={"answer": "Hello world"},
    )


async def test_stream_answer_langfuse_failure_yields_empty_trace_id(mocker):
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
