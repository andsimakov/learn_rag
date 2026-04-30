from langfuse import get_client, observe

from app.core import embedder, retriever
from app.core.llm import generate
from app.db.connection import get_pool
from app.schemas.query import QueryRequest, QueryResponse

_SYSTEM_PROMPT = (
    "You are an expert assistant for FastAPI documentation. "
    "Answer the user's question using ONLY the provided documentation excerpts. "
    "If the provided context is insufficient to answer fully, say so explicitly. "
    "Be concise and answer in plain prose — no markdown headers or bullet lists."
)


@observe(name="rag_query")
async def _answer(request: QueryRequest) -> QueryResponse:
    lf = get_client()
    lf.set_current_trace_io(input={"question": request.question, "top_k": request.top_k})

    pool = get_pool()

    vector = await embedder.embed(request.question)
    chunks = await retriever.search(pool, vector, request.top_k)
    answer_text = await generate(
        question=request.question,
        chunks=chunks,
        system_prompt=_SYSTEM_PROMPT,
    )

    trace_id = lf.get_current_trace_id() or ""
    lf.set_current_trace_io(output={"answer": answer_text})

    return QueryResponse(answer=answer_text, sources=chunks, trace_id=trace_id)


class QueryService:
    async def answer(self, request: QueryRequest) -> QueryResponse:
        return await _answer(request)
