"""Deterministic weighted-RRF fusion with explainable overlap deduplication."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import isfinite

from repo_dive.parsing.models import Chunk
from repo_dive.retrieval.lexical import LexicalHit
from repo_dive.retrieval.structural import StructuralHit
from repo_dive.retrieval.vector import VectorHit

DEFAULT_RRF_K = 60
DEFAULT_OVERLAP_THRESHOLD = 0.8


@dataclass(frozen=True, slots=True)
class FusionParameters:
    """Stable weighted-RRF and overlap-deduplication parameters."""

    rrf_k: int = DEFAULT_RRF_K
    lexical_weight: float = 1.0
    structural_weight: float = 1.0
    vector_weight: float = 0.0
    overlap_threshold: float = DEFAULT_OVERLAP_THRESHOLD

    def __post_init__(self) -> None:
        if self.rrf_k < 0:
            raise ValueError("rrf_k must not be negative")
        weights = (self.lexical_weight, self.structural_weight, self.vector_weight)
        if any(not isfinite(weight) or weight < 0.0 for weight in weights):
            raise ValueError("each channel weight must be finite and non-negative")
        if not any(weight > 0.0 for weight in weights):
            raise ValueError("at least one channel weight must be positive")
        if not isfinite(self.overlap_threshold) or not (
            0.0 < self.overlap_threshold <= 1.0
        ):
            raise ValueError("overlap_threshold must be greater than 0 and at most 1")


@dataclass(frozen=True, slots=True)
class FusionMetadata:
    """Parameters required to reproduce one fusion result."""

    strategy: str
    rrf_k: int
    channel_weights: tuple[tuple[str, float], ...]
    overlap_threshold: float


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One fused code-evidence hit with raw channel scores and reasons."""

    chunk: Chunk
    lexical_score: float | None
    structural_score: float | None
    vector_score: float | None
    fused_score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FusionResult:
    """Ranked hits and the metadata needed to explain their scores."""

    hits: tuple[SearchHit, ...]
    metadata: FusionMetadata


@dataclass(slots=True)
class _Candidate:
    chunk: Chunk
    lexical_score: float | None = None
    structural_score: float | None = None
    vector_score: float | None = None
    fused_score: float = 0.0
    reasons: list[str] = field(default_factory=list)


def fuse_hits(
    *,
    lexical_hits: Iterable[LexicalHit] = (),
    structural_hits: Iterable[StructuralHit] = (),
    vector_hits: Iterable[VectorHit] = (),
    parameters: FusionParameters | None = None,
    max_results: int = 20,
) -> FusionResult:
    """Fuse ranked channels without assigning ranks to absent evidence."""
    if max_results < 0:
        raise ValueError("max_results must not be negative")
    configured = parameters or FusionParameters()
    channel_weights = [
        ("lexical", configured.lexical_weight),
        ("structural", configured.structural_weight),
    ]
    if configured.vector_weight > 0.0:
        channel_weights.append(("vector", configured.vector_weight))
    metadata = FusionMetadata(
        strategy="weighted_rrf",
        rrf_k=configured.rrf_k,
        channel_weights=tuple(channel_weights),
        overlap_threshold=configured.overlap_threshold,
    )
    if max_results == 0:
        return FusionResult(hits=(), metadata=metadata)

    candidates: dict[str, _Candidate] = {}
    if configured.lexical_weight > 0.0:
        for rank, lexical_hit in enumerate(_rank_lexical(lexical_hits), start=1):
            candidate = _candidate(candidates, lexical_hit.chunk)
            candidate.lexical_score = lexical_hit.lexical_score
            contribution = _rrf_contribution(
                rank=rank,
                weight=configured.lexical_weight,
                rrf_k=configured.rrf_k,
            )
            candidate.fused_score += contribution
            for term in lexical_hit.matched_terms:
                _add_reason(candidate, f"lexical_match:{term}")
            _add_reason(
                candidate,
                _rrf_reason(
                    channel="lexical",
                    rank=rank,
                    weight=configured.lexical_weight,
                    contribution=contribution,
                ),
            )

    if configured.structural_weight > 0.0:
        for rank, structural_hit in enumerate(
            _rank_structural(structural_hits), start=1
        ):
            candidate = _candidate(candidates, structural_hit.chunk)
            candidate.structural_score = structural_hit.structural_score
            contribution = _rrf_contribution(
                rank=rank,
                weight=configured.structural_weight,
                rrf_k=configured.rrf_k,
            )
            candidate.fused_score += contribution
            for reason in structural_hit.reasons:
                _add_reason(candidate, reason)
            _add_reason(
                candidate,
                _rrf_reason(
                    channel="structural",
                    rank=rank,
                    weight=configured.structural_weight,
                    contribution=contribution,
                ),
            )

    if configured.vector_weight > 0.0:
        for rank, vector_hit in enumerate(_rank_vector(vector_hits), start=1):
            candidate = _candidate(candidates, vector_hit.chunk)
            candidate.vector_score = vector_hit.vector_score
            contribution = _rrf_contribution(
                rank=rank,
                weight=configured.vector_weight,
                rrf_k=configured.rrf_k,
            )
            candidate.fused_score += contribution
            _add_reason(
                candidate,
                _rrf_reason(
                    channel="vector",
                    rank=rank,
                    weight=configured.vector_weight,
                    contribution=contribution,
                ),
            )

    hits = tuple(
        SearchHit(
            chunk=candidate.chunk,
            lexical_score=candidate.lexical_score,
            structural_score=candidate.structural_score,
            vector_score=candidate.vector_score,
            fused_score=candidate.fused_score,
            reasons=tuple(candidate.reasons),
        )
        for candidate in candidates.values()
    )
    deduplicated = _deduplicate_overlaps(
        hits,
        overlap_threshold=configured.overlap_threshold,
    )
    return FusionResult(
        hits=tuple(sorted(deduplicated, key=_ranking_key)[:max_results]),
        metadata=metadata,
    )


def _rank_lexical(hits: Iterable[LexicalHit]) -> tuple[LexicalHit, ...]:
    ranked = tuple(hits)
    _validate_channel_hits(
        ((hit.chunk, hit.lexical_score) for hit in ranked),
        channel="lexical",
    )
    return tuple(
        sorted(
            ranked,
            key=lambda hit: (
                -hit.lexical_score,
                hit.chunk.path,
                hit.chunk.start_line,
                hit.chunk.id,
            ),
        )
    )


def _rank_structural(hits: Iterable[StructuralHit]) -> tuple[StructuralHit, ...]:
    ranked = tuple(hits)
    _validate_channel_hits(
        ((hit.chunk, hit.structural_score) for hit in ranked),
        channel="structural",
    )
    return tuple(
        sorted(
            ranked,
            key=lambda hit: (
                -hit.structural_score,
                hit.chunk.path,
                hit.chunk.start_line,
                hit.chunk.id,
            ),
        )
    )


def _rank_vector(hits: Iterable[VectorHit]) -> tuple[VectorHit, ...]:
    ranked = tuple(hits)
    chunk_ids: set[str] = set()
    for hit in ranked:
        if hit.chunk.id in chunk_ids:
            raise ValueError("vector channel contains duplicate Chunk IDs")
        chunk_ids.add(hit.chunk.id)
        if not isfinite(hit.vector_score):
            raise ValueError("vector scores must be finite")
    return tuple(
        sorted(
            ranked,
            key=lambda hit: (
                -hit.vector_score,
                hit.chunk.path,
                hit.chunk.start_line,
                hit.chunk.id,
            ),
        )
    )


def _validate_channel_hits(
    hits: Iterable[tuple[Chunk, float]],
    *,
    channel: str,
) -> None:
    chunk_ids: set[str] = set()
    for chunk, score in hits:
        if chunk.id in chunk_ids:
            raise ValueError(f"{channel} channel contains duplicate Chunk IDs")
        chunk_ids.add(chunk.id)
        if not isfinite(score) or score < 0.0:
            raise ValueError(f"{channel} scores must be finite and non-negative")


def _candidate(candidates: dict[str, _Candidate], chunk: Chunk) -> _Candidate:
    candidate = candidates.get(chunk.id)
    if candidate is None:
        candidate = _Candidate(chunk=chunk)
        candidates[chunk.id] = candidate
    elif candidate.chunk != chunk:
        raise ValueError("fusion channels reference conflicting Chunks for one ID")
    return candidate


def _rrf_contribution(*, rank: int, weight: float, rrf_k: int) -> float:
    return weight / (rrf_k + rank)


def _rrf_reason(
    *,
    channel: str,
    rank: int,
    weight: float,
    contribution: float,
) -> str:
    return (
        f"rrf:{channel}:rank={rank},weight={weight:.6f},"
        f"contribution={contribution:.12f}"
    )


def _add_reason(candidate: _Candidate, reason: str) -> None:
    if reason and reason not in candidate.reasons:
        candidate.reasons.append(reason)


def _deduplicate_overlaps(
    hits: tuple[SearchHit, ...],
    *,
    overlap_threshold: float,
) -> tuple[SearchHit, ...]:
    preferred = sorted(hits, key=_information_key)
    retained: list[SearchHit] = []
    for hit in preferred:
        if any(
            _is_overlapping_duplicate(
                hit,
                existing,
                overlap_threshold=overlap_threshold,
            )
            for existing in retained
        ):
            continue
        retained.append(hit)
    return tuple(retained)


def _is_overlapping_duplicate(
    left: SearchHit,
    right: SearchHit,
    *,
    overlap_threshold: float,
) -> bool:
    if left.chunk.path != right.chunk.path:
        return False
    if (
        left.chunk.symbol_id is not None
        and right.chunk.symbol_id is not None
        and left.chunk.symbol_id != right.chunk.symbol_id
    ):
        return False

    intersection = (
        min(left.chunk.end_line, right.chunk.end_line)
        - max(
            left.chunk.start_line,
            right.chunk.start_line,
        )
        + 1
    )
    if intersection <= 0:
        return False
    left_lines = left.chunk.end_line - left.chunk.start_line + 1
    right_lines = right.chunk.end_line - right.chunk.start_line + 1
    return intersection / min(left_lines, right_lines) >= overlap_threshold


def _information_key(hit: SearchHit) -> tuple[object, ...]:
    channel_count = sum(
        score is not None
        for score in (hit.lexical_score, hit.structural_score, hit.vector_score)
    )
    line_count = hit.chunk.end_line - hit.chunk.start_line + 1
    return (
        -(hit.chunk.symbol_id is not None),
        -len(hit.chunk.text.strip()),
        -line_count,
        -channel_count,
        -hit.fused_score,
        hit.chunk.path,
        hit.chunk.start_line,
        hit.chunk.end_line,
        hit.chunk.id,
    )


def _ranking_key(hit: SearchHit) -> tuple[object, ...]:
    return (
        -hit.fused_score,
        hit.chunk.path,
        hit.chunk.start_line,
        hit.chunk.end_line,
        hit.chunk.id,
    )


__all__ = [
    "DEFAULT_OVERLAP_THRESHOLD",
    "DEFAULT_RRF_K",
    "FusionMetadata",
    "FusionParameters",
    "FusionResult",
    "SearchHit",
    "fuse_hits",
]
