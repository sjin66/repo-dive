"""Pure deterministic planning and freshness checks for scope Evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from repo_dive.errors import RepositoryError
from repo_dive.knowledge_map.models import (
    FactNode,
    KnowledgeMapArtifact,
    RetrievalParameters,
    ScopeContract,
    canonical_sha256,
)
from repo_dive.parsing.models import Chunk, Symbol

_SYMBOL_KIND_ORDER = {
    "module": 0,
    "class": 1,
    "function": 2,
    "method": 3,
    "reference": 4,
}


@dataclass(frozen=True, slots=True)
class PlannedChunk:
    """One mandatory complete Chunk and every anchor represented by it."""

    chunk: Chunk
    anchor_fact_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScopeEvidencePlan:
    """Timestamp-free retrieval intent for one persisted scope contract."""

    contract: ScopeContract
    query: str
    query_plan_hash: str
    required_chunks: tuple[PlannedChunk, ...]


def plan_scope_evidence(
    artifact: KnowledgeMapArtifact,
    scope_id: str,
    *,
    chunks: tuple[Chunk, ...],
    symbols: tuple[Symbol, ...],
    retrieval_parameters: RetrievalParameters,
) -> ScopeEvidencePlan:
    """Resolve persisted anchors to complete Chunks with stable fallback order."""
    contract = next(
        (item for item in artifact.scope_contracts if item.scope_id == scope_id), None
    )
    if contract is None:
        raise RepositoryError(
            "knowledge_map_scope_not_found",
            "Knowledge Map scope does not exist.",
            details={
                "recovery_action": "select_current_scope",
                "retry_mode": "after_recovery",
                "scope_id": scope_id,
            },
        )
    nodes = {item.id: item for item in artifact.nodes}
    symbols_by_id = {item.id: item for item in symbols}
    chunks_by_symbol: dict[str, list[Chunk]] = {}
    chunks_by_path: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        chunks_by_path.setdefault(chunk.path, []).append(chunk)
        if chunk.symbol_id is not None:
            chunks_by_symbol.setdefault(chunk.symbol_id, []).append(chunk)

    selected: list[PlannedChunk] = []
    positions: dict[str, int] = {}
    for anchor_id in contract.required_anchor_fact_node_ids:
        selected_chunk = _representative_chunk(
            node_id=anchor_id,
            nodes=nodes,
            symbols_by_id=symbols_by_id,
            chunks_by_symbol=chunks_by_symbol,
            chunks_by_path=chunks_by_path,
        )
        if selected_chunk is None:
            raise RepositoryError(
                "knowledge_map_evidence_unavailable",
                "A required Knowledge Map anchor has no complete indexed Chunk.",
                details={
                    "anchor_fact_node_id": anchor_id,
                    "recovery_action": "make_source_indexable_or_select_scope",
                    "retry_mode": "after_recovery",
                    "scope_id": scope_id,
                },
            )
        prior = positions.get(selected_chunk.id)
        if prior is None:
            positions[selected_chunk.id] = len(selected)
            selected.append(PlannedChunk(selected_chunk, (anchor_id,)))
        else:
            current = selected[prior]
            selected[prior] = PlannedChunk(
                current.chunk, (*current.anchor_fact_node_ids, anchor_id)
            )

    allowed_nodes = [nodes[item] for item in contract.allowed_fact_node_ids]
    query_parts: list[str] = [contract.scope_kind]
    query_parts.extend(
        dict.fromkeys(
            value for node in allowed_nodes for value in (node.name, node.path) if value
        )
    )
    query = " ".join(query_parts)
    query_plan_hash = canonical_sha256(
        {
            "scope_contract_hash": contract.contract_hash,
            "ordered_anchor_fact_node_ids": list(
                contract.required_anchor_fact_node_ids
            ),
            "required_chunk_ids": [item.chunk.id for item in selected],
            "query": query,
            "retrieval_parameters": retrieval_parameters.to_document(),
        }
    )
    return ScopeEvidencePlan(contract, query, query_plan_hash, tuple(selected))


def _representative_chunk(
    *,
    node_id: str,
    nodes: Mapping[str, FactNode],
    symbols_by_id: dict[str, Symbol],
    chunks_by_symbol: dict[str, list[Chunk]],
    chunks_by_path: dict[str, list[Chunk]],
) -> Chunk | None:
    node = nodes[node_id]
    kind = node.kind
    if kind == "symbol":
        parser_id = node.parser_symbol_id
        direct = chunks_by_symbol.get(parser_id, ()) if parser_id is not None else ()
        if direct:
            return min(direct, key=_chunk_key)
        parent_id = node.parent_id
        assert parent_id is not None
        return _representative_chunk(
            node_id=parent_id,
            nodes=nodes,
            symbols_by_id=symbols_by_id,
            chunks_by_symbol=chunks_by_symbol,
            chunks_by_path=chunks_by_path,
        )
    if kind == "file":
        path = node.path
        assert path is not None
        candidates = chunks_by_path.get(path, ())
        definitions = [item for item in candidates if item.symbol_id in symbols_by_id]
        if definitions:
            return min(
                definitions,
                key=lambda item: _definition_key(
                    item, symbols_by_id[_required_symbol_id(item)]
                ),
            )
        return min(candidates, key=_chunk_key, default=None)
    if kind == "module":
        files = sorted(
            (
                item
                for item in nodes.values()
                if item.kind == "file" and item.parent_id == node_id
            ),
            key=lambda item: (item.path, item.id),
        )
        for file_node in files:
            candidate = _representative_chunk(
                node_id=file_node.id,
                nodes=nodes,
                symbols_by_id=symbols_by_id,
                chunks_by_symbol=chunks_by_symbol,
                chunks_by_path=chunks_by_path,
            )
            if candidate is not None:
                return candidate
        return None
    return min(
        (item for values in chunks_by_path.values() for item in values),
        key=_chunk_key,
        default=None,
    )


def _chunk_key(chunk: Chunk) -> tuple[object, ...]:
    return (chunk.path, chunk.start_line, chunk.end_line, chunk.id)


def _definition_key(chunk: Chunk, symbol: Symbol) -> tuple[object, ...]:
    return (
        chunk.path,
        chunk.start_line,
        chunk.end_line,
        _SYMBOL_KIND_ORDER.get(symbol.kind, len(_SYMBOL_KIND_ORDER)),
        symbol.qualified_name,
        symbol.id,
        chunk.id,
    )


def _required_symbol_id(chunk: Chunk) -> str:
    assert chunk.symbol_id is not None
    return chunk.symbol_id


__all__ = ["PlannedChunk", "ScopeEvidencePlan", "plan_scope_evidence"]
