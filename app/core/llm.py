from collections.abc import AsyncIterator
from functools import lru_cache

import anthropic
from langfuse import get_client, observe

from app.config import get_settings
from app.schemas.query import RetrievedChunk


class LLMOverloadedError(Exception):
    """LLM provider is temporarily over capacity."""


@lru_cache(maxsize=1)
def _get_client() -> anthropic.AsyncAnthropic:
    settings = get_settings()
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


@observe(as_type="generation")
async def generate(
    question: str,
    chunks: list[RetrievedChunk],
    system_prompt: str,
) -> str:
    """Call Claude with the retrieved context. Recorded as a generation in LangFuse."""
    settings = get_settings()
    client = _get_client()
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

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.max_tokens,
        system=system_prompt,
        messages=messages,
    )

    answer = response.content[0].text

    lf.update_current_generation(
        output=answer,
        usage_details={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )

    return answer


async def stream_generate(
    question: str,
    chunks: list[RetrievedChunk],
    system_prompt: str,
) -> AsyncIterator[str]:
    settings = get_settings()
    client = _get_client()

    context = "\n\n---\n\n".join(f"[{chunk.source_url}]\n{chunk.content}" for chunk in chunks)
    messages = [
        {
            "role": "user",
            "content": f"<context>\n{context}\n</context>\n\nQuestion: {question}",
        }
    ]

    async with client.messages.stream(
        model=settings.anthropic_model,
        max_tokens=settings.max_tokens,
        system=system_prompt,
        messages=messages,
    ) as stream:
        try:
            async for text in stream.text_stream:
                yield text
        except anthropic.APIStatusError as exc:
            body = exc.body if isinstance(exc.body, dict) else {}
            if body.get("error", {}).get("type") == "overloaded_error":
                raise LLMOverloadedError from exc
            raise
