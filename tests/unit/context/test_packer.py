from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from repo_dive.context.packer import (
    EvidencePacker,
    ExclusionReason,
)
from repo_dive.parsing.models import create_chunk
from repo_dive.retrieval.fusion import SearchHit


class ZeroEstimator:
    name = "zero-test-estimator"

    def estimate(self, text: str) -> int:
        return 0


def hit(
    path: str,
    start_line: int,
    text: str,
    score: float,
    *,
    symbol_id: str | None = None,
) -> SearchHit:
    line_count = max(1, len(text.splitlines()))
    chunk = create_chunk(
        path=path,
        start_line=start_line,
        end_line=start_line + line_count - 1,
        text=text,
        symbol_id=symbol_id,
    )
    return SearchHit(
        chunk=chunk,
        lexical_score=score,
        structural_score=None,
        vector_score=None,
        fused_score=score,
        reasons=(f"score:{score}",),
    )


def test_reserves_envelope_and_never_splits_evidence_to_fit() -> None:
    candidate = hit(
        "src/service.py",
        10,
        "def run():\n    value = prepare()\n    return value\n",
        1.0,
        symbol_id="service.run",
    )
    packer = EvidencePacker(envelope_reserve=12, item_metadata_reserve=8)

    roomy = packer.pack("run implementation", (candidate,), token_budget=1_000)
    exact = packer.pack(
        "run implementation",
        (candidate,),
        token_budget=roomy.estimated_tokens,
    )
    too_small = packer.pack(
        "run implementation",
        (candidate,),
        token_budget=roomy.estimated_tokens - 1,
    )

    assert roomy.estimator == "conservative_utf8_bytes_v1"
    assert roomy.reserved_tokens >= 12
    assert roomy.estimated_tokens <= roomy.budget
    assert exact.items == roomy.items
    assert exact.estimated_tokens == roomy.estimated_tokens
    assert exact.items[0].hit.chunk.text == candidate.chunk.text
    assert exact.items[0].hit.chunk.start_line == 10
    assert exact.items[0].hit.chunk.end_line == 12
    assert too_small.items == ()
    assert too_small.truncated is True
    assert too_small.excluded[0].reason is ExclusionReason.BUDGET


def test_prioritizes_implementations_limits_each_file_and_explains_exclusions() -> None:
    primary = hit("src/a.py", 1, "def primary(): pass", 0.9, symbol_id="a.primary")
    secondary = hit(
        "src/a.py",
        10,
        "def secondary(): pass",
        0.8,
        symbol_id="a.secondary",
    )
    capped = hit("src/a.py", 20, "def capped(): pass", 0.7, symbol_id="a.capped")
    diverse = hit("src/b.py", 1, "def diverse(): pass", 0.6, symbol_id="b.diverse")
    prose = hit("README.md", 1, "primary architecture", 0.99)
    low = hit("src/low.py", 1, "def low(): pass", 0.1, symbol_id="low")
    duplicate = replace(primary, fused_score=0.05)
    packer = EvidencePacker(
        estimator=ZeroEstimator(),
        envelope_reserve=1,
        item_metadata_reserve=1,
        max_items_per_file=2,
        min_fused_score=0.2,
    )

    bundle = packer.pack(
        "architecture",
        (prose, low, capped, secondary, diverse, duplicate, primary),
        token_budget=10,
    )

    assert [item.hit.chunk.id for item in bundle.items] == [
        primary.chunk.id,
        secondary.chunk.id,
        diverse.chunk.id,
        prose.chunk.id,
    ]
    assert Counter(item.hit.chunk.path for item in bundle.items)["src/a.py"] == 2
    assert {item.reason for item in bundle.excluded} == {
        ExclusionReason.BUDGET,
        ExclusionReason.DUPLICATE,
        ExclusionReason.LOW_SCORE,
    }
    assert bundle.truncated is True
    assert bundle.estimated_tokens == 5
    assert bundle == packer.pack(
        "architecture",
        tuple(reversed((prose, low, capped, secondary, diverse, duplicate, primary))),
        token_budget=10,
    )


def test_tiny_budget_returns_empty_truncated_bundle() -> None:
    candidate = hit("src/a.py", 1, "def a(): pass", 1.0, symbol_id="a")
    packer = EvidencePacker(
        estimator=ZeroEstimator(),
        envelope_reserve=5,
        item_metadata_reserve=1,
    )

    bundle = packer.pack("a", (candidate,), token_budget=4)

    assert bundle.items == ()
    assert bundle.reserved_tokens == 4
    assert bundle.estimated_tokens == 4
    assert bundle.estimated_tokens <= bundle.budget
    assert bundle.truncated is True
    assert bundle.excluded[0].reason is ExclusionReason.BUDGET


def test_usage_never_exceeds_budget_and_is_monotonic() -> None:
    candidates = tuple(
        hit(
            f"src/{index % 3}.py",
            index * 10 + 1,
            f"def item_{index}():\n    return {'value ' * (index + 1)}\n",
            1.0 - index / 20,
            symbol_id=f"item_{index}",
        )
        for index in range(8)
    )
    packer = EvidencePacker(max_items_per_file=3)

    bundles = [
        packer.pack("items", candidates, token_budget=budget)
        for budget in range(0, 301, 5)
    ]
    usage = [bundle.estimated_tokens for bundle in bundles]

    assert all(bundle.estimated_tokens <= bundle.budget for bundle in bundles)
    assert usage == sorted(usage)


def test_invalid_packer_options_and_conflicting_duplicates_are_rejected() -> None:
    with pytest.raises(ValueError, match="reserve"):
        EvidencePacker(envelope_reserve=-1)
    with pytest.raises(ValueError, match="max_items_per_file"):
        EvidencePacker(max_items_per_file=0)
    with pytest.raises(ValueError, match="min_fused_score"):
        EvidencePacker(min_fused_score=-0.1)

    candidate = hit("src/a.py", 1, "def a(): pass", 1.0, symbol_id="a")
    conflicting = replace(candidate, chunk=replace(candidate.chunk, text="different"))
    with pytest.raises(ValueError, match="conflicting Chunks"):
        EvidencePacker().pack("a", (candidate, conflicting), token_budget=100)
    with pytest.raises(ValueError, match="token_budget"):
        EvidencePacker().pack("a", (candidate,), token_budget=-1)
