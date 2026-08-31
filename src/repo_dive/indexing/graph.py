"""Bounded, deterministic queries over the persisted Symbol graph."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol

from repo_dive.parsing.models import Relationship, Symbol


class RelationshipDirection(StrEnum):
    """Which directed relationship endpoints may expand a frontier."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """A relationship enriched with both endpoint source locations."""

    source: Symbol
    target: Symbol
    kind: str
    confidence: float
    provenance: str


@dataclass(frozen=True, slots=True)
class GraphTraversal:
    """Stable graph evidence bounded by caller-supplied limits."""

    roots: tuple[Symbol, ...]
    nodes: tuple[Symbol, ...]
    edges: tuple[GraphEdge, ...]
    truncated: bool


class GraphReader(Protocol):
    """Narrow persistence operations required by SymbolGraph."""

    def query_symbols(
        self,
        query: str,
        *,
        path: str | None,
        max_results: int,
    ) -> tuple[Symbol, ...]: ...

    def get_symbols_by_id(self, symbol_ids: tuple[str, ...]) -> tuple[Symbol, ...]: ...

    def query_relationships(
        self,
        symbol_ids: tuple[str, ...],
        *,
        direction: Literal["outgoing", "incoming", "both"],
        edge_kinds: tuple[str, ...] | None,
        limit: int,
        min_confidence: float = 0.0,
    ) -> tuple[Relationship, ...]: ...


class SymbolGraph:
    """Search Symbols and traverse their relationships without unbounded reads."""

    def __init__(self, reader: GraphReader) -> None:
        self._reader = reader

    def find_symbols(
        self,
        query: str,
        *,
        path: str | None = None,
        max_results: int = 20,
    ) -> tuple[Symbol, ...]:
        """Return exact then case-folded name matches in stable source order."""
        if not query:
            raise ValueError("symbol query must not be empty")
        if max_results <= 0:
            raise ValueError("max_results must be positive")
        return self._reader.query_symbols(
            query,
            path=path,
            max_results=max_results,
        )

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
    ) -> GraphTraversal:
        """Breadth-first traversal with explicit depth, node, and edge budgets."""
        _validate_limits(
            depth=depth,
            max_nodes=max_nodes,
            max_edges=max_edges,
            min_confidence=min_confidence,
        )
        normalized_kinds = (
            tuple(sorted(set(edge_kinds))) if edge_kinds is not None else None
        )
        unique_root_ids = tuple(dict.fromkeys(root_ids))
        selected_root_ids = unique_root_ids[:max_nodes]
        root_by_id = {
            symbol.id: symbol
            for symbol in self._reader.get_symbols_by_id(selected_root_ids)
        }
        roots = tuple(
            root_by_id[symbol_id]
            for symbol_id in selected_root_ids
            if symbol_id in root_by_id
        )
        nodes = list(roots)
        node_by_id = {symbol.id: symbol for symbol in roots}
        frontier = tuple(symbol.id for symbol in roots)
        edges: list[GraphEdge] = []
        edge_keys: set[tuple[str, str, str]] = set()
        truncated = len(unique_root_ids) > max_nodes

        for _ in range(depth):
            if not frontier or len(edges) >= max_edges:
                break
            remaining_edges = max_edges - len(edges)
            relationships = self._reader.query_relationships(
                frontier,
                direction=direction.value,
                edge_kinds=normalized_kinds,
                limit=remaining_edges + 1,
                min_confidence=min_confidence,
            )
            if len(relationships) > remaining_edges:
                relationships = relationships[:remaining_edges]
                truncated = True

            pending_ids: list[str] = []
            pending_set: set[str] = set()
            accepted_relationships: list[Relationship] = []
            frontier_set = set(frontier)
            for relationship in relationships:
                key = _relationship_key(relationship)
                if key in edge_keys:
                    continue
                adjacent_ids = _adjacent_ids(
                    relationship,
                    frontier_set=frontier_set,
                    direction=direction,
                )
                if not adjacent_ids:
                    continue

                fits = True
                for symbol_id in adjacent_ids:
                    if symbol_id in node_by_id or symbol_id in pending_set:
                        continue
                    if len(nodes) + len(pending_ids) >= max_nodes:
                        truncated = True
                        fits = False
                        break
                    pending_ids.append(symbol_id)
                    pending_set.add(symbol_id)
                if fits:
                    accepted_relationships.append(relationship)

            discovered = {
                symbol.id: symbol
                for symbol in self._reader.get_symbols_by_id(tuple(pending_ids))
            }
            next_frontier: list[str] = []
            for symbol_id in pending_ids:
                symbol = discovered.get(symbol_id)
                if symbol is None:
                    continue
                node_by_id[symbol_id] = symbol
                nodes.append(symbol)
                next_frontier.append(symbol_id)

            for relationship in accepted_relationships:
                source = node_by_id.get(relationship.source_id)
                target = node_by_id.get(relationship.target_id)
                if source is None or target is None:
                    continue
                edge_keys.add(_relationship_key(relationship))
                edges.append(
                    GraphEdge(
                        source=source,
                        target=target,
                        kind=relationship.kind,
                        confidence=relationship.confidence,
                        provenance=relationship.provenance,
                    )
                )

            frontier = tuple(next_frontier)

        return GraphTraversal(
            roots=roots,
            nodes=tuple(nodes),
            edges=tuple(edges),
            truncated=truncated,
        )


def _validate_limits(
    *,
    depth: int,
    max_nodes: int,
    max_edges: int,
    min_confidence: float,
) -> None:
    if depth < 0:
        raise ValueError("depth must not be negative")
    if max_nodes <= 0:
        raise ValueError("max_nodes must be positive")
    if max_edges <= 0:
        raise ValueError("max_edges must be positive")
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1")


def _relationship_key(
    relationship: Relationship,
) -> tuple[str, str, str]:
    return (
        relationship.source_id,
        relationship.target_id,
        relationship.kind,
    )


def _adjacent_ids(
    relationship: Relationship,
    *,
    frontier_set: set[str],
    direction: RelationshipDirection,
) -> tuple[str, ...]:
    adjacent: list[str] = []
    if (
        direction in {RelationshipDirection.OUTGOING, RelationshipDirection.BOTH}
        and relationship.source_id in frontier_set
    ):
        adjacent.append(relationship.target_id)
    if (
        direction in {RelationshipDirection.INCOMING, RelationshipDirection.BOTH}
        and relationship.target_id in frontier_set
        and relationship.source_id not in adjacent
    ):
        adjacent.append(relationship.source_id)
    return tuple(adjacent)


__all__ = [
    "GraphEdge",
    "GraphTraversal",
    "RelationshipDirection",
    "SymbolGraph",
]
