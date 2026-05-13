from collections.abc import AsyncGenerator
from functools import lru_cache

import anthropic
from langfuse import get_client, observe

from app.config import get_settings
from app.schemas.query import RetrievedChunk


class LLMOverloadedError(Exception):
    """LLM provider is temporarily over capacity."""


def is_overloaded(exc: anthropic.APIStatusError) -> bool:
    body = exc.body if isinstance(exc.body, dict) else {}
    return body.get("error", {}).get("type") == "overloaded_error"


@lru_cache(maxsize=1)
def get_client_cached() -> anthropic.AsyncAnthropic:
    settings = get_settings()
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())


@observe(as_type="generation")
async def generate(
    question: str,
    chunks: list[RetrievedChunk],
    system_prompt: str,
) -> str:
    """Call Claude with the retrieved context. Recorded as a generation in LangFuse."""
    settings = get_settings()
    client = get_client_cached()
    lf = get_client()

    context = "\n\n---\n\n".join(f"[{chunk.source_url}]\n{chunk.content}" for chunk in chunks)
    messages = [
        {
            "role": "user",
            "content": f"<context>\n{context}\n</context>\n\nQuestion: {question}",
        }
    ]

    lf.update_current_generation(
        name="llm_call",
        model=settings.anthropic_model,
        input=messages,
        metadata={"system": system_prompt},
    )

    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.max_tokens,
            system=system_prompt,
            messages=messages,
        )
    except anthropic.APIStatusError as exc:
        if is_overloaded(exc):
            raise LLMOverloadedError from exc
        raise

    if not response.content or response.content[0].type != "text":
        raise ValueError("LLM returned an empty or non-text response")
    answer_text = response.content[0].text

    lf.update_current_generation(
        output=answer_text,
        usage_details={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )

    return answer_text


async def stream_generate(
    question: str,
    chunks: list[RetrievedChunk],
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    # Tracing is handled by the caller (query_service.stream_answer) because
    # @observe does not support async generators.
    settings = get_settings()
    client = get_client_cached()

    context = "\n\n---\n\n".join(f"[{chunk.source_url}]\n{chunk.content}" for chunk in chunks)
    messages = [
        {
            "role": "user",
            "content": f"<context>\n{context}\n</context>\n\nQuestion: {question}",
        }
    ]

    try:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=settings.max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
    except anthropic.APIStatusError as exc:
        if is_overloaded(exc):
            raise LLMOverloadedError from exc
        raise
