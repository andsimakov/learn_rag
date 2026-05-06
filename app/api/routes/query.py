import json
import logging
from collections.abc import AsyncIterator

import anthropic
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import answer, stream_answer

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    try:
        return await answer(request)
    except Exception as exc:
        log.exception("Query failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc


@router.post("/query/stream")
async def query_stream(request: QueryRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in stream_answer(request):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            log.exception("Stream failed")
            overloaded = (
                isinstance(exc, anthropic.APIStatusError)
                and isinstance(exc.body, dict)
                and exc.body.get("error", {}).get("type") == "overloaded_error"
            )
            msg = (
                "The AI service is temporarily overloaded — please try again in a moment."
                if overloaded
                else "Something went wrong. Please try again."
            )
            yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
