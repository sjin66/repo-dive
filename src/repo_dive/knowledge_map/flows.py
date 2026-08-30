"""Bounded static flow candidates, reading tour, and semantic scope contracts."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, replace

from repo_dive.knowledge_map.models import (
    Cluster,
    FactEdge,
    FactNode,
    ScopeContract,
    StaticFlow,
    TourItem,
    stable_id,
)

_UTILITY_NAMES = frozenset({"__init__", "get", "set", "identity", "noop"})


@dataclass(frozen=True, slots=True)
class FlowAnalysis:
    flows: tuple[StaticFlow, ...]
    included_count: int
    omitted_count: int
    no_roots: bool
    truncation_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TourAnalysis:
    items: tuple[TourItem, ...]
    included_count: int
    omitted_count: int


def derive_static_flows(
    nodes: tuple[FactNode, ...],
    edges: tuple[FactEdge, ...],
    *,
    flow_budget: int,
    flow_depth: int,
    nodes_per_flow: int,
    edges_per_flow: int,
    script_entrypoints: tuple[str, ...] = (),
) -> FlowAnalysis:
    """Traverse closed calls/imports adjacency without claiming runtime execution."""
    by_id = {node.id: node for node in nodes}
    edge_by_adjacency: dict[tuple[str, str, str], FactEdge] = {}
    adjacency: dict[str, list[tuple[str, str, FactEdge]]] = defaultdict(list)
    for edge in edges:
        if edge.origin != "parser" or edge.kind not in {"calls", "imports"}:
            continue
        key = (edge.source_id, edge.target_id, edge.kind)
        current = edge_by_adjacency.get(key)
        if current is None or (-edge.confidence_max, edge.id) < (
            -current.confidence_max,
            current.id,
        ):
            edge_by_adjacency[key] = edge
    for (source_id, target_id, kind), edge in sorted(edge_by_adjacency.items()):
        adjacency[source_id].append((target_id, kind, edge))
    roots = tuple(
        sorted(
            (
                node
                for node in nodes
                if node.kind == "symbol"
                and (
                    node.name.rsplit(".", 1)[-1] in {"main", "entrypoint"}
                    or (node.path or "").endswith("__main__.py")
                    or node.name in script_entrypoints
                )
            ),
            key=lambda item: (
                item.importance_rank.as_tuple()
                if item.importance_rank is not None
                else (0, 0, 0, 0, 0, item.path or "", item.id),
                item.id,
            ),
        )
    )
    if not roots:
        return FlowAnalysis((), 0, 0, True, ())
    candidates: list[StaticFlow] = []
    suppressed = 0
    truncation_reasons: set[str] = set()
    work_budget = flow_budget * max(nodes_per_flow, 1) * 4
    work = 0
    for root_index, root in enumerate(roots):
        root_kind = (
            "project_script"
            if root.name in script_entrypoints
            else "main_module"
            if (root.path or "").endswith("__main__.py")
            else "named_entrypoint"
        )
        queue: deque[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], bool]] = (
            deque([((root.id,), (), (), False)])
        )
        while queue:
            if work >= work_budget:
                suppressed += len(queue) + len(roots) - root_index - 1
                truncation_reasons.add("candidate_budget")
                queue.clear()
                break
            work += 1
            path, edge_ids, transitions, truncated = queue.popleft()
            neighbors = tuple(adjacency.get(path[-1], ()))
            allowed = tuple(item for item in neighbors if item[0] not in path)
            depth_reached = len(edge_ids) >= flow_depth
            size_reached = (
                len(path) >= nodes_per_flow or len(edge_ids) >= edges_per_flow
            )
            if not allowed or depth_reached or size_reached:
                reason = (
                    "depth_limit"
                    if depth_reached
                    else "size_limit"
                    if size_reached
                    else "cycle"
                    if neighbors and not allowed
                    else "terminal"
                )
                leaf = by_id[path[-1]]
                leaf_name = leaf.name.rsplit(".", 1)[-1]
                is_non_bridge_utility = leaf_name in _UTILITY_NAMES and (
                    leaf.importance_signals is None
                    or not leaf.importance_signals.cross_module_bridge
                )
                if is_non_bridge_utility and reason == "terminal":
                    flow_id = stable_id(
                        "flow", *path[:-1], "utility_suppressed", path[-1]
                    )
                    candidates.append(
                        StaticFlow(
                            id=flow_id,
                            root_node_id=root.id,
                            step_node_ids=path[:-1] or (root.id,),
                            edge_ids=edge_ids[:-1],
                            transition_kinds=transitions[:-1],
                            terminal_reason="utility_suppressed",
                            confidence=min(
                                (
                                    edge_by_adjacency_key(edge_id, edges).confidence_min
                                    for edge_id in edge_ids[:-1]
                                ),
                                default=1.0,
                            ),
                            incomplete_coverage=any(
                                kind == "imports" for kind in transitions[:-1]
                            ),
                            truncated=False,
                            root_kind=root_kind,
                            transition_semantics=tuple(
                                "runtime_call"
                                if kind == "calls"
                                else "structural_import_fallback"
                                for kind in transitions[:-1]
                            ),
                            representative_relationship_ids=tuple(
                                edge_by_adjacency_key(edge_id, edges).relationship_id
                                or ""
                                for edge_id in edge_ids[:-1]
                            ),
                            execution_semantics="static",
                            import_fallback=any(
                                kind == "imports" for kind in transitions[:-1]
                            ),
                            suppressed_utility_node_ids=(path[-1],),
                        )
                    )
                    truncation_reasons.add("utility_suppressed")
                    continue
                confidence = min(
                    (
                        edge_by_adjacency_key(edge_id, edges).confidence_min
                        for edge_id in edge_ids
                    ),
                    default=1.0,
                )
                flow_id = stable_id("flow", *path, *edge_ids)
                representative_ids = tuple(
                    edge_by_adjacency_key(edge_id, edges).relationship_id or ""
                    for edge_id in edge_ids
                )
                transition_semantics = tuple(
                    "runtime_call" if kind == "calls" else "structural_import_fallback"
                    for kind in transitions
                )
                candidates.append(
                    StaticFlow(
                        id=flow_id,
                        root_node_id=root.id,
                        step_node_ids=path,
                        edge_ids=edge_ids,
                        transition_kinds=transitions,
                        terminal_reason=reason,
                        confidence=confidence,
                        incomplete_coverage=any(
                            kind == "imports" for kind in transitions
                        )
                        or any(
                            (by_id[item].language or "") != "python" for item in path
                        ),
                        truncated=truncated or depth_reached or size_reached,
                        root_kind=root_kind,
                        transition_semantics=transition_semantics,
                        representative_relationship_ids=representative_ids,
                        execution_semantics="static",
                        import_fallback=any(kind == "imports" for kind in transitions),
                    )
                )
                continue
            for target_id, kind, edge in allowed:
                queue.append(
                    (
                        (*path, target_id),
                        (*edge_ids, edge.id),
                        (*transitions, kind),
                        truncated,
                    )
                )
    # Exact-sequence dedupe and no-prefix emission are deterministic.
    unique = {(flow.step_node_ids, flow.transition_kinds): flow for flow in candidates}
    paths = tuple(unique)
    useful = tuple(
        unique[path]
        for path in sorted(paths)
        if unique[path].terminal_reason == "utility_suppressed"
        or not any(
            len(other[0]) > len(path[0])
            and other[0][: len(path[0])] == path[0]
            and other[1][: len(path[1])] == path[1]
            for other in paths
        )
    )
    kept = tuple(
        sorted(useful, key=lambda item: (item.step_node_ids, item.id))[:flow_budget]
    )
    omitted = suppressed + len(candidates) - len(unique) + len(unique) - len(useful)
    omitted += max(0, len(useful) - len(kept))
    if len(useful) > len(kept):
        truncation_reasons.add("flow_budget")
    return FlowAnalysis(
        flows=kept,
        included_count=len(kept),
        omitted_count=omitted,
        no_roots=False,
        truncation_reasons=tuple(sorted(truncation_reasons)),
    )


def derive_tour(
    nodes: tuple[FactNode, ...],
    clusters: tuple[Cluster, ...],
    flows: tuple[StaticFlow, ...],
    *,
    tour_budget: int,
) -> TourAnalysis:
    """Order entrypoints, clusters, flows, then uncovered bridge modules once."""
    candidates: list[tuple[tuple[int | str, ...], str, str, str | None]] = []
    for node in nodes:
        if (
            node.kind == "symbol"
            and node.importance_signals is not None
            and node.importance_signals.entrypoint
        ):
            rank = (
                node.importance_rank.as_tuple()
                if node.importance_rank is not None
                else (0, 0, 0, 0, 0, node.path or "", node.id)
            )
            candidates.append(((0, *rank), "node", node.id, node.id))
    for cluster in clusters:
        candidates.append(((1, cluster.id), "cluster", cluster.id, None))
    for flow in flows:
        candidates.append(((2, flow.id), "flow", flow.id, None))
    covered_modules = {
        node.parent_id
        for node in nodes
        if node.kind == "file"
        and any(node.id in cluster.member_node_ids for cluster in clusters)
    }
    for node in nodes:
        if (
            node.kind == "module"
            and node.id not in covered_modules
            and node.importance_signals is not None
            and node.importance_signals.cross_module_bridge
        ):
            rank = (
                node.importance_rank.as_tuple()
                if node.importance_rank is not None
                else (0, 0, 0, 0, 0, "", node.id)
            )
            candidates.append(((3, *rank), "node", node.id, node.id))
    ordered = sorted(candidates, key=lambda item: item[0])[:tour_budget]
    preliminary = tuple(
        TourItem(
            stable_id("tour", kind, target_id),
            kind,
            target_id,
            fact_node_id,
            rank,
            None,
        )
        for rank, kind, target_id, fact_node_id in ordered
    )
    items = tuple(
        replace(
            item,
            next_item_id=(
                preliminary[index + 1].id if index + 1 < len(preliminary) else None
            ),
        )
        for index, item in enumerate(preliminary)
    )
    return TourAnalysis(
        items=items,
        included_count=len(items),
        omitted_count=max(0, len(candidates) - len(items)),
    )


def derive_scope_contracts(
    nodes: tuple[FactNode, ...],
    clusters: tuple[Cluster, ...],
    flows: tuple[StaticFlow, ...],
    tour: tuple[TourItem, ...],
) -> tuple[ScopeContract, ...]:
    """Freeze exact closed fact expansion and claim permissions per scope."""
    by_id = {node.id: node for node in nodes}

    def ancestors(node_id: str) -> tuple[str, ...]:
        values: list[str] = []
        current: str | None = node_id
        while current is not None and current in by_id:
            values.append(current)
            current = by_id[current].parent_id
        return tuple(values)

    contracts: list[ScopeContract] = []
    for cluster in clusters:
        allowed: list[str] = []
        for member in cluster.member_node_ids:
            owned_symbols = tuple(
                node.id
                for node in nodes
                if node.kind == "symbol" and node.parent_id == member
            )
            if owned_symbols:
                for symbol_id in owned_symbols:
                    allowed.extend(ancestors(symbol_id))
            else:
                allowed.extend(ancestors(member))
        contracts.append(
            ScopeContract.create(
                scope_id=cluster.id,
                scope_kind="cluster",
                allowed_fact_node_ids=tuple(dict.fromkeys(allowed)),
                required_anchor_fact_node_ids=cluster.member_node_ids,
                allowed_record_kinds=("cluster_label", "concept"),
                allowed_claim_kinds=(
                    "label",
                    "summary",
                    "responsibility",
                    "association",
                    "concept_description",
                ),
            )
        )
    for flow in flows:
        allowed = []
        for node_id in flow.step_node_ids:
            allowed.extend(ancestors(node_id))
        contracts.append(
            ScopeContract.create(
                scope_id=flow.id,
                scope_kind="flow",
                allowed_fact_node_ids=tuple(dict.fromkeys(allowed)),
                required_anchor_fact_node_ids=tuple(dict.fromkeys(flow.step_node_ids)),
                allowed_record_kinds=("flow_explanation", "concept"),
                allowed_claim_kinds=(
                    "label",
                    "summary",
                    "flow_explanation",
                    "association",
                    "concept_description",
                ),
            )
        )
    contract_by_scope = {item.scope_id: item for item in contracts}
    for item in tour:
        if item.target_kind in {"cluster", "flow"}:
            target = contract_by_scope[item.target_id]
            allowed_ids = target.allowed_fact_node_ids
            anchors = target.required_anchor_fact_node_ids
        else:
            assert item.fact_node_id is not None
            allowed_ids = tuple(dict.fromkeys(ancestors(item.fact_node_id)))
            anchors = (item.fact_node_id,)
        contracts.append(
            ScopeContract.create(
                scope_id=item.id,
                scope_kind="tour",
                allowed_fact_node_ids=allowed_ids,
                required_anchor_fact_node_ids=anchors,
                allowed_record_kinds=("reading_guidance", "concept"),
                allowed_claim_kinds=(
                    "label",
                    "summary",
                    "reading_guidance",
                    "association",
                    "concept_description",
                ),
            )
        )
    return tuple(sorted(contracts, key=lambda item: (item.scope_kind, item.scope_id)))


def edge_by_adjacency_key(edge_id: str, edges: tuple[FactEdge, ...]) -> FactEdge:
    for edge in edges:
        if edge.id == edge_id:
            return edge
    raise ValueError("flow edge does not exist")
