"""Explainable structural retrieval over Symbols and source Chunks."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from repo_dive.indexing.graph import (
    GraphEdge,
    GraphTraversal,
    RelationshipDirection,
)
from repo_dive.parsing.models import Chunk, Symbol

DEFAULT_RELATIONSHIP_KINDS = ("calls", "contains", "imports", "inherits")


@dataclass(frozen=True, slots=True)
class StructuralHit:
    """One structurally-ranked Chunk with transparent ranking reasons."""

    chunk: Chunk
    structural_score: float
    reasons: tuple[str, ...]


class StructuralGraph(Protocol):
    """Narrow Symbol lookup boundary required by structural retrieval."""

    def find_symbols(
        self,
        query: str,
        *,
        path: str | None = None,
        max_results: int = 20,
    ) -> tuple[Symbol, ...]: ...

    def neighbors(
        self,
        root_ids: tuple[str, ...],
        *,
        direction: RelationshipDirection = RelationshipDirection.BOTH,
        depth: int = 1,
        edge_kinds: tuple[str, ...] | None = None,
        max_nodes: int = 100,
        max_edges: int = 400,
        min_confidence: float = 0.0,
    ) -> GraphTraversal: ...


@dataclass(slots=True)
class _HitState:
    chunk: Chunk
    score: float
    reasons: list[str]


@dataclass(frozen=True, slots=True)
class _PathStep:
    edge: GraphEdge
    target: Symbol
    reverse: bool


class _ChunkLookup:
    def __init__(self, chunks: Iterable[Chunk]) -> None:
        self._definitions: dict[str, list[Chunk]] = {}
        self._by_path: dict[str, list[Chunk]] = {}
        chunk_ids: set[str] = set()
        for chunk in chunks:
            if chunk.id in chunk_ids:
                raise ValueError("structural corpus contains duplicate Chunk IDs")
            chunk_ids.add(chunk.id)
            if chunk.symbol_id is not None:
                self._definitions.setdefault(chunk.symbol_id, []).append(chunk)
            self._by_path.setdefault(chunk.path, []).append(chunk)

    def for_symbol(self, symbol: Symbol) -> tuple[tuple[Chunk, bool], ...]:
        definitions = self._definitions.get(symbol.id, ())
        if definitions:
            return tuple((chunk, True) for chunk in definitions)
        return tuple(
            (chunk, False)
            for chunk in self._by_path.get(symbol.path, ())
            if chunk.start_line <= symbol.start_line <= chunk.end_line
        )


def search_structural(
    query: str,
    *,
    graph: StructuralGraph,
    chunks: Iterable[Chunk],
    path: str | None = None,
    max_results: int = 20,
    depth: int = 1,
    max_nodes: int = 100,
    max_edges: int = 400,
    min_confidence: float = 0.75,
    relationship_kinds: tuple[str, ...] = DEFAULT_RELATIONSHIP_KINDS,
) -> tuple[StructuralHit, ...]:
    """Return stable Symbol matches and bounded relationship expansions."""
    _validate_options(
        max_results=max_results,
        depth=depth,
        max_nodes=max_nodes,
        max_edges=max_edges,
        min_confidence=min_confidence,
    )
    normalized_query = query.strip()
    if not normalized_query or max_results == 0:
        return ()

    chunk_lookup = _ChunkLookup(chunks)
    roots = graph.find_symbols(
        normalized_query,
        path=path,
        max_results=max_nodes,
    )
    states: dict[str, _HitState] = {}
    for root in roots:
        reason, match_score = _symbol_match(normalized_query, root)
        for chunk, is_definition in chunk_lookup.for_symbol(root):
            score = match_score * (1.0 if is_definition else 0.5)
            _add_hit(states, chunk=chunk, score=score, reason=reason)

    if depth > 0 and roots:
        traversal = graph.neighbors(
            tuple(root.id for root in roots),
            direction=RelationshipDirection.BOTH,
            depth=depth,
            edge_kinds=relationship_kinds,
            max_nodes=max_nodes,
            max_edges=max_edges,
            min_confidence=min_confidence,
        )
        root_scores = {
            root.id: _symbol_match(normalized_query, root)[1] for root in roots
        }
        for symbol, root, steps in _relationship_paths(
            traversal,
            min_confidence=min_confidence,
        ):
            if not steps:
                continue
            score = root_scores[root.id]
            for step in steps:
                score *= step.edge.confidence
            score /= len(steps) + 1
            reason = _format_relationship_path(root, steps)
            for chunk, is_definition in chunk_lookup.for_symbol(symbol):
                candidate_score = score * (1.0 if is_definition else 0.5)
                _add_hit(
                    states,
                    chunk=chunk,
                    score=candidate_score,
                    reason=reason,
                )

    return _ranked_hits(states, max_results=max_results)


def _relationship_paths(
    traversal: GraphTraversal,
    *,
    min_confidence: float,
) -> tuple[tuple[Symbol, Symbol, tuple[_PathStep, ...]], ...]:
    adjacency: dict[str, list[_PathStep]] = {}
    for edge in traversal.edges:
        if edge.confidence < min_confidence:
            continue
        adjacency.setdefault(edge.source.id, []).append(
            _PathStep(edge=edge, target=edge.target, reverse=False)
        )
        adjacency.setdefault(edge.target.id, []).append(
            _PathStep(edge=edge, target=edge.source, reverse=True)
        )
    for adjacent_steps in adjacency.values():
        adjacent_steps.sort(
            key=lambda step: (
                step.reverse,
                step.edge.kind,
                step.target.path,
                step.target.start_line,
                step.target.id,
            )
        )

    discovered: dict[str, tuple[Symbol, tuple[_PathStep, ...]]] = {
        root.id: (root, ()) for root in traversal.roots
    }
    queue = deque(traversal.roots)
    while queue:
        current = queue.popleft()
        root, path = discovered[current.id]
        for step in adjacency.get(current.id, ()):
            if step.target.id in discovered:
                continue
            discovered[step.target.id] = (root, (*path, step))
            queue.append(step.target)

    paths: list[tuple[Symbol, Symbol, tuple[_PathStep, ...]]] = []
    for node in traversal.nodes:
        if node.id not in discovered:
            continue
        root, path_steps = discovered[node.id]
        paths.append((node, root, path_steps))
    return tuple(paths)


def _format_relationship_path(
    root: Symbol,
    steps: tuple[_PathStep, ...],
) -> str:
    reason = f"relationship_path:{root.qualified_name}"
    for step in steps:
        edge = step.edge
        detail = (
            f"{edge.kind}[confidence={edge.confidence:.3f},source={edge.provenance}]"
        )
        connector = f" <-{detail}- " if step.reverse else f" -{detail}-> "
        reason += f"{connector}{step.target.qualified_name}"
    return reason


def _symbol_match(query: str, symbol: Symbol) -> tuple[str, float]:
    if symbol.qualified_name == query:
        match_kind, score = "qualified_name_exact", 1.0
    elif symbol.name == query:
        match_kind, score = "name_exact", 0.95
    elif symbol.qualified_name.casefold() == query.casefold():
        match_kind, score = "qualified_name_normalized", 0.9
    else:
        match_kind, score = "name_normalized", 0.85
    return f"symbol_match:{match_kind}:{symbol.qualified_name}", score


def _add_hit(
    states: dict[str, _HitState],
    *,
    chunk: Chunk,
    score: float,
    reason: str,
) -> None:
    state = states.get(chunk.id)
    if state is None:
        states[chunk.id] = _HitState(chunk=chunk, score=score, reasons=[reason])
        return
    state.score = max(state.score, score)
    if reason not in state.reasons:
        state.reasons.append(reason)


def _ranked_hits(
    states: dict[str, _HitState],
    *,
    max_results: int,
) -> tuple[StructuralHit, ...]:
    hits = [
        StructuralHit(
            chunk=state.chunk,
            structural_score=state.score,
            reasons=tuple(state.reasons),
        )
        for state in states.values()
    ]
    hits.sort(
        key=lambda hit: (
            -hit.structural_score,
            hit.chunk.path,
            hit.chunk.start_line,
            hit.chunk.id,
        )
    )
    return tuple(hits[:max_results])


def _validate_options(
    *,
    max_results: int,
    depth: int,
    max_nodes: int,
    max_edges: int,
    min_confidence: float,
) -> None:
    if max_results < 0:
        raise ValueError("max_results must not be negative")
    if depth < 0:
        raise ValueError("depth must not be negative")
    if max_nodes <= 0 or max_edges <= 0:
        raise ValueError("graph budgets must be positive")
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1")


__all__ = [
    "DEFAULT_RELATIONSHIP_KINDS",
    "StructuralHit",
    "search_structural",
]
