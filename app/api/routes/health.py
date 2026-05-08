from fastapi import APIRouter, HTTPException, status

from app.db.connection import ping_pool

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, str]:
    try:
        await ping_pool()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return {"status": "ok"}
