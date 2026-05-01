from pydantic import BaseModel, Field

from app.config import get_settings


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default_factory=lambda: get_settings().top_k_default, ge=1, le=20)


class RetrievedChunk(BaseModel):
    content: str
    source_url: str
    heading: str | None
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[RetrievedChunk]
    trace_id: str
