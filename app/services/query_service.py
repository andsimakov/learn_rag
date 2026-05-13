import logging
from collections.abc import AsyncGenerator

from langfuse import get_client, observe

from app.core import embedder, retriever
from app.core.llm import generate, stream_generate
from app.schemas.query import QueryRequest, QueryResponse

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert assistant for FastAPI documentation. "
    "Answer the user's question using ONLY the provided documentation excerpts. "
    "If the provided context is insufficient to answer fully, say so explicitly. "
    "Be concise and answer in plain prose — no markdown headers or bullet lists."
)


@observe(name="rag_query")
async def answer(request: QueryRequest) -> QueryResponse:
    lf = get_client()
    lf.set_current_trace_io(input={"question": request.question, "top_k": request.top_k})

    vector = await embedder.embed(request.question)
    chunks = await retriever.search(vector, request.question, request.top_k)
    if not chunks:
        return QueryResponse(answer="No relevant documentation found.", sources=[], trace_id="")
    answer_text = await generate(
        question=request.question,
        chunks=chunks,
        system_prompt=_SYSTEM_PROMPT,
    )

    trace_id = lf.get_current_trace_id() or ""
    lf.set_current_trace_io(output={"answer": answer_text})

    return QueryResponse(answer=answer_text, sources=chunks, trace_id=trace_id)


async def stream_answer(request: QueryRequest) -> AsyncGenerator[dict, None]:
    # @observe cannot decorate async generators — trace manually after streaming completes.
    vector = await embedder.embed(request.question)
    chunks = await retriever.search(vector, request.question, request.top_k)

    if not chunks:
        yield {"type": "sources", "sources": []}
        yield {"type": "token", "text": "No relevant documentation found."}
        yield {"type": "done", "trace_id": ""}
        return

    yield {"type": "sources", "sources": [c.model_dump() for c in chunks]}

    tokens: list[str] = []
    try:
        async for token in stream_generate(request.question, chunks, _SYSTEM_PROMPT):
            tokens.append(token)
            yield {"type": "token", "text": token}
    finally:
        trace_id = ""
        try:
            lf = get_client()
            trace = lf.trace(
                name="rag_stream",
                input={"question": request.question, "top_k": request.top_k},
                output={"answer": "".join(tokens)},
            )
            trace_id = trace.id
        except Exception:
            log.warning("LangFuse trace failed", exc_info=True)
        yield {"type": "done", "trace_id": trace_id}
