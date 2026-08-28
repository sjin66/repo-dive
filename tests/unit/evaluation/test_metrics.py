from __future__ import annotations

import pytest

from repo_dive.evaluation.metrics import (
    aggregate_metric,
    budget_compliance,
    citation_coverage,
    hit_rate,
    recall_at_k,
    reciprocal_rank,
)


def test_hand_calculated_retrieval_metrics() -> None:
    ranked = ("chunk-a", "chunk-b", "chunk-c", "chunk-b")
    relevant = ("chunk-b", "chunk-d")

    assert recall_at_k(ranked, relevant, k=3) == pytest.approx(0.5)
    assert reciprocal_rank(ranked, relevant) == pytest.approx(0.5)
    assert hit_rate(("src/b.py",), ("src/a.py", "src/b.py")) == pytest.approx(0.5)


def test_budget_and_citation_metrics_are_explicit_and_optional() -> None:
    assert budget_compliance(estimated_tokens=80, token_budget=100) == 1.0
    assert budget_compliance(estimated_tokens=101, token_budget=100) == 0.0
    assert citation_coverage(("e1", "e3"), ("e1", "e2")) == pytest.approx(0.5)
    assert citation_coverage((), ()) is None


def test_aggregate_ignores_not_applicable_metrics() -> None:
    assert aggregate_metric((1.0, None, 0.5)) == {
        "evaluated_cases": 2,
        "mean": 0.75,
    }
    assert aggregate_metric((None,)) == {"evaluated_cases": 0, "mean": None}


@pytest.mark.parametrize("k", [0, -1])
def test_recall_rejects_invalid_k(k: int) -> None:
    with pytest.raises(ValueError, match="k must be positive"):
        recall_at_k(("a",), ("a",), k=k)
