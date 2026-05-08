import json
import re

import anthropic
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.core.llm import LLMOverloadedError, get_client_cached, is_overloaded
from app.schemas.query import RetrievedChunk


class EvalScore(BaseModel):
    model_config = ConfigDict(extra="ignore")

    faithfulness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    reasoning: str


_JUDGE_PROMPT = """\
You are evaluating a RAG (Retrieval-Augmented Generation) system answer.

Question: {question}

Retrieved context used by the system:
{context}

Generated answer: {answer}

Reference answer: {reference_answer}

Score the generated answer on two dimensions (integer 1–5):

- faithfulness: Is every claim in the generated answer supported by the retrieved context?
  5 = fully grounded in context, no unsupported claims
  1 = contradicts context or ignores it entirely

- relevance: Does the generated answer address the question?
  5 = complete, direct, and accurate answer
  1 = misses the point or answers a different question

Respond with JSON only — no markdown, no prose:
{{"faithfulness": <int>, "relevance": <int>, "reasoning": "<one sentence>"}}"""


async def judge(
    question: str,
    chunks: list[RetrievedChunk],
    answer: str,
    reference_answer: str,
) -> EvalScore:
    """Use Claude as a judge to score a RAG answer on faithfulness and relevance."""
    settings = get_settings()
    client = get_client_cached()

    context = "\n\n---\n\n".join(f"[{chunk.source_url}]\n{chunk.content}" for chunk in chunks)

    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.judge_max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": _JUDGE_PROMPT.format(
                        question=question,
                        context=context,
                        answer=answer,
                        reference_answer=reference_answer,
                    ),
                }
            ],
        )
    except anthropic.APIStatusError as exc:
        if is_overloaded(exc):
            raise LLMOverloadedError from exc
        raise RuntimeError("Judge LLM call failed") from exc

    if not response.content or response.content[0].type != "text":
        raise ValueError("Judge received an empty or non-text response from LLM")
    text = response.content[0].text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object in judge response: {text!r}")
    data = json.loads(match.group())
    return EvalScore.model_validate(data)
