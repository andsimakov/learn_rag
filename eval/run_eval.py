"""
Offline evaluation — measures RAG quality against a golden dataset.

    python -m eval.run_eval

Requires the ingestion pipeline to have run first and the DB to be up.
"""

import asyncio
import json
from pathlib import Path

from app.db.connection import close_pool, create_pool
from app.schemas.query import QueryRequest
from app.services.query_service import QueryService
from eval.judge import judge

_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
_COL_W = 55  # truncation width for question column in report


async def run() -> None:
    dataset = json.loads(_DATASET_PATH.read_text())

    await create_pool()
    service = QueryService()

    results = []
    print(f"\nEvaluating {len(dataset)} questions…\n")

    for entry in dataset:
        question: str = entry["question"]
        reference: str = entry["reference_answer"]

        response = await service.answer(QueryRequest(question=question))
        score = await judge(question, response.sources, response.answer, reference)

        results.append(
            {
                "question": question,
                "faithfulness": score.faithfulness,
                "relevance": score.relevance,
                "reasoning": score.reasoning,
            }
        )

        q_display = question[:_COL_W] + "…" if len(question) > _COL_W else question
        print(f"Q: {q_display}")
        print(f"   Faithfulness {score.faithfulness}/5  Relevance {score.relevance}/5")
        print(f"   {score.reasoning}\n")

    sep = "─" * (_COL_W + 30)
    print(sep)
    avg_f = sum(r["faithfulness"] for r in results) / len(results)
    avg_r = sum(r["relevance"] for r in results) / len(results)
    print(f"Average  —  Faithfulness: {avg_f:.1f}/5   Relevance: {avg_r:.1f}/5")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
