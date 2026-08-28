"""Deterministic selection of complete, diverse evidence under a token budget."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from repo_dive.context.tokens import ConservativeTokenEstimator, TokenEstimator
from repo_dive.parsing.models import Chunk
from repo_dive.retrieval.fusion import SearchHit

DEFAULT_ENVELOPE_RESERVE = 64
DEFAULT_ITEM_METADATA_RESERVE = 24
DEFAULT_MAX_ITEMS_PER_FILE = 2


class ExclusionReason(StrEnum):
    """Stable reason why a candidate was not included in an evidence bundle."""

    DUPLICATE = "duplicate"
    BUDGET = "budget"
    LOW_SCORE = "low_score"


@dataclass(frozen=True, slots=True)
class ExcludedEvidence:
    """One omitted candidate and its machine-readable reason."""

    chunk_id: str
    path: str
    reason: ExclusionReason


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One complete SearchHit selected for downstream generation."""

    id: str
    hit: SearchHit
    estimated_tokens: int

    @property
    def evidence_id(self) -> str:
        """Return the stable evidence identity using an explicit public name."""
        return self.id


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """A complete evidence selection and its deterministic budget accounting."""

    query: str
    budget: int
    estimated_tokens: int
    reserved_tokens: int
    truncated: bool
    estimator: str
    items: tuple[EvidenceItem, ...]
    excluded: tuple[ExcludedEvidence, ...]

    @property
    def token_budget(self) -> int:
        """Return the configured budget using the CLI-facing field name."""
        return self.budget


class EvidencePacker:
    """Select high-value implementation evidence without partial Chunks."""

    def __init__(
        self,
        *,
        estimator: TokenEstimator | None = None,
        envelope_reserve: int = DEFAULT_ENVELOPE_RESERVE,
        item_metadata_reserve: int = DEFAULT_ITEM_METADATA_RESERVE,
        max_items_per_file: int = DEFAULT_MAX_ITEMS_PER_FILE,
        min_fused_score: float = 0.0,
    ) -> None:
        if envelope_reserve < 0 or item_metadata_reserve < 0:
            raise ValueError("token reserves must not be negative")
        if max_items_per_file <= 0:
            raise ValueError("max_items_per_file must be positive")
        if not isfinite(min_fused_score) or min_fused_score < 0.0:
            raise ValueError("min_fused_score must be finite and non-negative")

        self._estimator = estimator or ConservativeTokenEstimator()
        if not self._estimator.name:
            raise ValueError("estimator name must not be empty")
        self._envelope_reserve = envelope_reserve
        self._item_metadata_reserve = item_metadata_reserve
        self._max_items_per_file = max_items_per_file
        self._min_fused_score = min_fused_score

    def pack(
        self,
        query: str,
        hits: Iterable[SearchHit],
        *,
        token_budget: int,
    ) -> EvidenceBundle:
        """Pack complete evidence with stable ranking and exclusion diagnostics."""
        if token_budget < 0:
            raise ValueError("token_budget must not be negative")

        required_reserve = self._envelope_reserve + self._estimate(query)
        reserved_tokens = min(token_budget, required_reserve)
        estimated_tokens = reserved_tokens
        items: list[EvidenceItem] = []
        excluded: list[ExcludedEvidence] = []
        file_counts: dict[str, int] = {}
        chunks_by_id: dict[str, Chunk] = {}

        ranked = sorted(tuple(hits), key=_ranking_key)
        for hit in ranked:
            _validate_hit(hit)
            previous_chunk = chunks_by_id.get(hit.chunk.id)
            if previous_chunk is not None:
                if previous_chunk != hit.chunk:
                    raise ValueError(
                        "evidence candidates reference conflicting Chunks for one ID"
                    )
                excluded.append(_excluded(hit, ExclusionReason.DUPLICATE))
                continue
            chunks_by_id[hit.chunk.id] = hit.chunk

            if hit.fused_score < self._min_fused_score:
                excluded.append(_excluded(hit, ExclusionReason.LOW_SCORE))
                continue

            evidence_id = _evidence_id(hit.chunk.id)
            item_tokens = (
                self._item_metadata_reserve
                + self._estimate(_metadata_text(evidence_id, hit))
                + self._estimate(hit.chunk.text)
            )
            if (
                file_counts.get(hit.chunk.path, 0) >= self._max_items_per_file
                or estimated_tokens + item_tokens > token_budget
            ):
                excluded.append(_excluded(hit, ExclusionReason.BUDGET))
                continue

            items.append(
                EvidenceItem(
                    id=evidence_id,
                    hit=hit,
                    estimated_tokens=item_tokens,
                )
            )
            file_counts[hit.chunk.path] = file_counts.get(hit.chunk.path, 0) + 1
            estimated_tokens += item_tokens

        return EvidenceBundle(
            query=query,
            budget=token_budget,
            estimated_tokens=estimated_tokens,
            reserved_tokens=reserved_tokens,
            truncated=bool(excluded),
            estimator=self._estimator.name,
            items=tuple(items),
            excluded=tuple(excluded),
        )

    def _estimate(self, text: str) -> int:
        estimate = self._estimator.estimate(text)
        if isinstance(estimate, bool) or not isinstance(estimate, int) or estimate < 0:
            raise ValueError("estimator must return a non-negative integer")
        return estimate


def _ranking_key(hit: SearchHit) -> tuple[object, ...]:
    return (
        hit.chunk.symbol_id is None,
        -hit.fused_score,
        hit.chunk.path,
        hit.chunk.start_line,
        hit.chunk.end_line,
        hit.chunk.id,
    )


def _validate_hit(hit: SearchHit) -> None:
    if not isfinite(hit.fused_score) or hit.fused_score < 0.0:
        raise ValueError("fused scores must be finite and non-negative")


def _evidence_id(chunk_id: str) -> str:
    digest = hashlib.sha256(chunk_id.encode("utf-8")).hexdigest()
    return f"evidence:{digest}"


def _metadata_text(evidence_id: str, hit: SearchHit) -> str:
    values = (
        evidence_id,
        hit.chunk.id,
        hit.chunk.path,
        str(hit.chunk.start_line),
        str(hit.chunk.end_line),
        hit.chunk.symbol_id or "",
        repr(hit.lexical_score),
        repr(hit.structural_score),
        repr(hit.vector_score),
        repr(hit.fused_score),
        *hit.reasons,
    )
    return "\n".join(values)


def _excluded(hit: SearchHit, reason: ExclusionReason) -> ExcludedEvidence:
    return ExcludedEvidence(
        chunk_id=hit.chunk.id,
        path=hit.chunk.path,
        reason=reason,
    )


__all__ = [
    "DEFAULT_ENVELOPE_RESERVE",
    "DEFAULT_ITEM_METADATA_RESERVE",
    "DEFAULT_MAX_ITEMS_PER_FILE",
    "EvidenceBundle",
    "EvidenceItem",
    "EvidencePacker",
    "ExcludedEvidence",
    "ExclusionReason",
]
