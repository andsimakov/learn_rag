from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_query_service
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import QueryService

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service),
) -> QueryResponse:
    try:
        return await service.answer(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
