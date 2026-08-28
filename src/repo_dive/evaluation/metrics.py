"""Small deterministic retrieval metrics with explicit not-applicable values."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from repo_dive.schema import JsonObject


def recall_at_k(
    ranked: Sequence[str],
    relevant: Iterable[str],
    *,
    k: int,
) -> float | None:
    """Return unique relevant-item recall within the first ``k`` ranks."""
    if k <= 0:
        raise ValueError("k must be positive")
    expected = set(relevant)
    if not expected:
        return None
    return len(expected.intersection(ranked[:k])) / len(expected)


def reciprocal_rank(
    ranked: Sequence[str],
    relevant: Iterable[str],
) -> float | None:
    """Return the reciprocal rank of the first relevant item."""
    expected = set(relevant)
    if not expected:
        return None
    for rank, item in enumerate(ranked, start=1):
        if item in expected:
            return 1.0 / rank
    return 0.0


def hit_rate(observed: Iterable[str], expected: Iterable[str]) -> float | None:
    """Return coverage of expected path or symbol identities."""
    required = set(expected)
    if not required:
        return None
    return len(required.intersection(observed)) / len(required)


def budget_compliance(*, estimated_tokens: int, token_budget: int) -> float:
    """Return one when non-negative accounting stays inside a positive budget."""
    if estimated_tokens < 0 or token_budget <= 0:
        raise ValueError("token accounting must be non-negative with a positive budget")
    return float(estimated_tokens <= token_budget)


def citation_coverage(
    cited: Iterable[str],
    required: Iterable[str],
) -> float | None:
    """Return coverage of required evidence identities or paths."""
    return hit_rate(cited, required)


def aggregate_metric(values: Iterable[float | None]) -> JsonObject:
    """Average applicable values without treating missing metrics as zero."""
    applicable = tuple(value for value in values if value is not None)
    return {
        "evaluated_cases": len(applicable),
        "mean": sum(applicable) / len(applicable) if applicable else None,
    }


__all__ = [
    "aggregate_metric",
    "budget_compliance",
    "citation_coverage",
    "hit_rate",
    "recall_at_k",
    "reciprocal_rank",
]
