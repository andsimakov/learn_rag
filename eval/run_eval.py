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
import logging  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from app.core.logging import configure_logging  # noqa: E402
from app.core.tracing import get_client  # noqa: E402
from app.db.connection import close_pool, create_pool  # noqa: E402
from app.schemas.query import QueryRequest  # noqa: E402
from app.services.query_service import answer  # noqa: E402
from eval.judge import judge  # noqa: E402

configure_logging()

logger = logging.getLogger(__name__)

_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
_RESULTS_DIR = Path(__file__).parent / "results"


async def run() -> None:
    dataset = json.loads(_DATASET_PATH.read_text())

    await create_pool()

    try:
        results = []
        logger.info("starting evaluation", extra={"total": len(dataset)})

        for i, entry in enumerate(dataset):
            question: str = entry["question"]
            reference: str = entry["reference_answer"]

            logger.info("evaluating question", extra={"index": i + 1, "total": len(dataset), "question": question})

            response = await answer(QueryRequest(question=question))
            score = await judge(question, response.sources, response.answer, reference)

            results.append(
                {
                    "question": question,
                    "faithfulness": score.faithfulness,
                    "relevance": score.relevance,
                    "reasoning": score.reasoning,
                }
            )

            logger.info(
                "question scored",
                extra={"faithfulness": score.faithfulness, "relevance": score.relevance, "reasoning": score.reasoning},
            )

        if not results:
            logger.warning("no results to score")
            return

        avg_f = sum(r["faithfulness"] for r in results) / len(results)
        avg_r = sum(r["relevance"] for r in results) / len(results)
        logger.info("evaluation complete", extra={"avg_faithfulness": avg_f, "avg_relevance": avg_r})

        _RESULTS_DIR.mkdir(exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
        out_path = _RESULTS_DIR / f"{ts}.json"
        out_path.write_text(
            json.dumps({"avg_faithfulness": avg_f, "avg_relevance": avg_r, "results": results}, indent=2)
        )
        logger.info("results saved", extra={"path": str(out_path)})
    finally:
        get_client().flush()
        await close_pool()


if __name__ == "__main__":
    _exit_code = 0
    try:
        asyncio.run(run())
    except Exception:
        logger.exception("eval failed")
        _exit_code = 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_exit_code)  # skip LangFuse/multiprocessing atexit handlers — already flushed above
