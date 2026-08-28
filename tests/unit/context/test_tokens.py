from __future__ import annotations

import pytest

from repo_dive.context.tokens import ConservativeTokenEstimator, TokenEstimator


def accepts_estimator(estimator: TokenEstimator) -> tuple[str, int]:
    return estimator.name, estimator.estimate("sample")


def test_conservative_estimator_counts_utf8_bytes_deterministically() -> None:
    estimator = ConservativeTokenEstimator(bytes_per_token=3)

    assert estimator.name == "conservative_utf8_bytes_v1"
    assert estimator.estimate("") == 0
    assert estimator.estimate("abc") == 1
    assert estimator.estimate("abcdef") == 2
    assert estimator.estimate("你") == 1
    assert estimator.estimate("😀") == 2
    assert accepts_estimator(estimator) == (
        "conservative_utf8_bytes_v1",
        2,
    )


def test_estimator_rejects_non_positive_ratio() -> None:
    with pytest.raises(ValueError, match="bytes_per_token"):
        ConservativeTokenEstimator(bytes_per_token=0)
