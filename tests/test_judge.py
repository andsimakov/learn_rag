"""Tests for EvalScore Pydantic model in eval/judge.py."""

import pytest
from pydantic import ValidationError

from eval.judge import EvalScore


def test_eval_score_valid_input():
    score = EvalScore(faithfulness=4, relevance=5, reasoning="Answer is grounded.")
    assert score.faithfulness == 4
    assert score.relevance == 5
    assert score.reasoning == "Answer is grounded."


def test_eval_score_ignores_extra_fields():
    score = EvalScore(
        faithfulness=3,
        relevance=3,
        reasoning="Partially relevant.",
        unknown_field="should be ignored",
    )
    assert score.faithfulness == 3
    assert not hasattr(score, "unknown_field")


def test_eval_score_raises_on_score_out_of_range():
    with pytest.raises(ValidationError):
        EvalScore(faithfulness=6, relevance=3, reasoning="Out of range.")


def test_eval_score_raises_on_missing_required_field():
    with pytest.raises(ValidationError):
        EvalScore(faithfulness=3, relevance=3)
