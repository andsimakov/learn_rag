"""
Offline evaluation — measures RAG quality against a golden dataset.

    python -m eval.run_eval

Requires the ingestion pipeline to have run first and the DB to be up.
"""

from dotenv import load_dotenv

# Must run before any LangFuse import — pydantic-settings does not write back to os.environ.
load_dotenv()

import asyncio  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

from langfuse import get_client  # noqa: E402

from app.db.connection import close_pool, create_pool  # noqa: E402
from app.schemas.query import QueryRequest  # noqa: E402
from app.services.query_service import QueryService  # noqa: E402
from eval.judge import judge  # noqa: E402

_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
_COL_W = 55  # truncation width for question column in report


async def run() -> None:
    dataset = json.loads(_DATASET_PATH.read_text())

    await create_pool()
    service = QueryService()

    results = []
    print(f"\nEvaluating {len(dataset)} questions…\n")

    for i, entry in enumerate(dataset):
        question: str = entry["question"]
        reference: str = entry["reference_answer"]

        q_display = question[:_COL_W] + "…" if len(question) > _COL_W else question
        print(f"[{i + 1}/{len(dataset)}] {q_display}", flush=True)

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

        print(f"   Faithfulness {score.faithfulness}/5  Relevance {score.relevance}/5")
        print(f"   {score.reasoning}\n")

    sep = "─" * (_COL_W + 30)
    print(sep)
    avg_f = sum(r["faithfulness"] for r in results) / len(results)
    avg_r = sum(r["relevance"] for r in results) / len(results)
    print(f"Average  —  Faithfulness: {avg_f:.1f}/5   Relevance: {avg_r:.1f}/5")

    get_client().flush()
    await close_pool()


if __name__ == "__main__":
    _exit_code = 0
    try:
        asyncio.run(run())
    except Exception:
        import traceback

        traceback.print_exc()
        _exit_code = 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_exit_code)  # skip LangFuse/multiprocessing atexit handlers — already flushed above
