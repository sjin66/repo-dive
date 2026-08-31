"""Explainable unique-neighbor importance signals and stable rank tuples."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from repo_dive.knowledge_map.models import (
    FactEdge,
    FactNode,
    ImportanceRank,
    ImportanceSignals,
)


def analyze_importance(
    nodes: tuple[FactNode, ...], edges: tuple[FactEdge, ...]
) -> tuple[FactNode, ...]:
    """Attach raw signals without allowing repeated occurrences to inflate rank."""
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    by_id = {node.id: node for node in nodes}

    def module_id(node_id: str) -> str | None:
        current = by_id.get(node_id)
        while current is not None and current.kind != "module":
            current = by_id.get(current.parent_id or "")
        return current.id if current is not None else None

    bridges: set[str] = set()
    documentation_sources: dict[str, set[str]] = defaultdict(set)
    test_sources: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        parser_or_aggregate = edge.origin == "parser" or (
            edge.origin == "derived"
            and edge.rule_id is not None
            and (
                edge.rule_id.startswith("aggregate_file_")
                or edge.rule_id.startswith("aggregate_module_")
            )
        )
        if parser_or_aggregate:
            pass
        else:
            continue
        outgoing[edge.source_id].add(edge.target_id)
        incoming[edge.target_id].add(edge.source_id)
        if module_id(edge.source_id) != module_id(edge.target_id):
            bridges.update((edge.source_id, edge.target_id))
        source = by_id.get(edge.source_id)
        source_path = (source.path if source is not None else "") or ""
        if source_path.startswith("docs/") or source_path.lower().endswith(
            ("readme.md", ".rst")
        ):
            documentation_sources[edge.target_id].add(source_path)
        if "/test" in f"/{source_path.lower()}" or source_path.lower().startswith(
            "test"
        ):
            test_sources[edge.target_id].add(source_path)
    result: list[FactNode] = []
    for node in nodes:
        path = node.path or ""
        leaf_name = node.name.rsplit(".", 1)[-1]
        entrypoint = int(
            node.kind == "symbol"
            and (leaf_name in {"main", "entrypoint"} or path.endswith("__main__.py"))
        )
        public_api = int(node.kind == "symbol" and not leaf_name.startswith("_"))
        fan_in = len(incoming[node.id])
        fan_out = len(outgoing[node.id])
        bridge = node.id in bridges
        signals = ImportanceSignals(
            unique_fan_in=fan_in,
            unique_fan_out=fan_out,
            cross_module_bridge=bridge,
            entrypoint=bool(entrypoint),
            public_api=bool(public_api),
            documentation_mentions=len(documentation_sources[node.id]),
            distinct_test_files=len(test_sources[node.id]),
        )
        rank = ImportanceRank(
            entrypoint=-entrypoint,
            unique_fan_in=-fan_in,
            cross_module_bridge=-int(bridge),
            unique_fan_out=-fan_out,
            public_api=-public_api,
            path=node.path or "",
            node_id=node.id,
        )
        result.append(replace(node, importance_signals=signals, importance_rank=rank))
    return tuple(result)
