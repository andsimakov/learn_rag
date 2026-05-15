import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.llm import LLMOverloadedError
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import answer, stream_answer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    try:
        return await answer(request)
    except LLMOverloadedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is temporarily overloaded — please try again in a moment.",
        ) from exc
    except Exception as exc:
        logger.exception("Query failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc


@router.post("/query/stream")
async def query_stream(request: QueryRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in stream_answer(request):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.exception("Stream failed")
            msg = (
                "The AI service is temporarily overloaded — please try again in a moment."
                if isinstance(exc, LLMOverloadedError)
                else "Something went wrong. Please try again."
            )
            yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
