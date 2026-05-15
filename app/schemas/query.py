from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.config import get_settings


class QueryRequest(BaseModel):
    question: Annotated[str, StringConstraints(min_length=1, max_length=1000, strip_whitespace=True)]
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
