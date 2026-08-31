"""Deterministic directory clusters, module SCCs, and closed architecture layers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from repo_dive.knowledge_map.models import (
    Cluster,
    CycleGroup,
    FactEdge,
    FactNode,
    Layer,
    stable_id,
)


@dataclass(frozen=True, slots=True)
class TopologyResult:
    clusters: tuple[Cluster, ...]
    layers: tuple[Layer, ...]
    strongly_connected_components: tuple[tuple[str, ...], ...]
    cycle_groups: tuple[CycleGroup, ...]
    omitted_clusters: int


def derive_topology(
    nodes: tuple[FactNode, ...],
    edges: tuple[FactEdge, ...],
    *,
    cluster_budget: int,
    minimum_cluster_files: int,
) -> TopologyResult:
    """Derive simple versioned structures using stable IDs and closed rules."""
    if cluster_budget <= 0 or minimum_cluster_files <= 0:
        raise ValueError("topology budgets must be positive")
    modules = tuple(node for node in nodes if node.kind == "module")
    files = tuple(node for node in nodes if node.kind == "file")
    groups = _initial_file_groups(files)
    merge_signals = _merge_undersized_groups(groups, edges, minimum_cluster_files)

    adjacency = _module_adjacency(modules, edges)
    sccs = _tarjan(tuple(module.id for module in modules), adjacency)
    module_edge_ids = {
        (edge.source_id, edge.target_id): edge.id
        for edge in edges
        if _is_module_dependency(edge, {item.id for item in modules})
    }
    cycle_groups = tuple(
        CycleGroup(
            id=stable_id("scc", *component),
            member_module_ids=component,
            edge_ids=tuple(
                sorted(
                    edge_id
                    for (source, target), edge_id in module_edge_ids.items()
                    if source in component and target in component
                )
            ),
        )
        for component in sccs
        if len(component) > 1
        or any(
            source == component[0] and target == component[0]
            for source, target in module_edge_ids
        )
    )
    scc_by_module = {
        member: group.id for group in cycle_groups for member in group.member_module_ids
    }
    scc_order = {group.id: index for index, group in enumerate(cycle_groups)}
    clusters: list[Cluster] = []
    for key, members in sorted(groups.items())[:cluster_budget]:
        member_ids = tuple(member.id for member in members)
        internal, external, internal_occurrences, external_occurrences = _edge_counts(
            set(member_ids), edges
        )
        clusters.append(
            Cluster(
                id=stable_id("cluster", "directory_v1", key, *member_ids),
                member_node_ids=member_ids,
                formation_signals=(
                    merge_signals.get(key, "package_directory_boundary_v1"),
                ),
                internal_unique_edges=internal,
                external_unique_edges=external,
                internal_occurrences=internal_occurrences,
                external_occurrences=external_occurrences,
                scc_ids=tuple(
                    sorted(
                        dict.fromkeys(
                            scc_by_module[module_id]
                            for module_id in (member.parent_id for member in members)
                            if module_id in scc_by_module
                        ),
                        key=scc_order.__getitem__,
                    )
                ),
            )
        )
    layers = _layers(modules)
    ordered_clusters = tuple(
        sorted(clusters, key=lambda item: (item.member_node_ids, item.id))
    )
    return TopologyResult(
        ordered_clusters,
        layers,
        sccs,
        cycle_groups,
        max(0, len(groups) - len(clusters)),
    )


def _initial_file_groups(files: tuple[FactNode, ...]) -> dict[str, list[FactNode]]:
    package_roots = sorted(
        {
            (file.path or "").rsplit("/", 1)[0] if "/" in (file.path or "") else "."
            for file in files
            if (file.path or "").endswith(("package.json", "pyproject.toml"))
        },
        key=lambda value: (-len(value), value),
    )
    groups: dict[str, list[FactNode]] = defaultdict(list)
    for file in sorted(files, key=lambda item: (item.path or "", item.id)):
        path = file.path or ""
        root = next(
            (
                candidate
                for candidate in package_roots
                if candidate == "."
                or path == candidate
                or path.startswith(f"{candidate}/")
            ),
            path.split("/", 1)[0] if "/" in path else ".",
        )
        groups[root].append(file)
    return dict(groups)


def _merge_undersized_groups(
    groups: dict[str, list[FactNode]],
    edges: tuple[FactEdge, ...],
    minimum: int,
) -> dict[str, str]:
    signals: dict[str, str] = {}
    while len(groups) > 1:
        undersized = tuple(key for key in sorted(groups) if len(groups[key]) < minimum)
        if not undersized:
            break
        source = undersized[0]
        source_ids = {item.id for item in groups[source]}
        candidates: list[tuple[int, str]] = []
        for target in sorted(key for key in groups if key != source):
            target_ids = {item.id for item in groups[target]}
            connectivity = sum(
                edge.occurrence_count
                for edge in edges
                if (edge.source_id in source_ids and edge.target_id in target_ids)
                or (edge.target_id in source_ids and edge.source_id in target_ids)
            )
            candidates.append((-connectivity, target))
        _, target = min(candidates)
        groups[target] = sorted(
            (*groups[target], *groups.pop(source)),
            key=lambda item: (item.path or "", item.id),
        )
        signals[target] = "maximum_connectivity_undersized_merge_v1"
    return signals


def _module_adjacency(
    modules: tuple[FactNode, ...], edges: tuple[FactEdge, ...]
) -> dict[str, tuple[str, ...]]:
    module_ids = {item.id for item in modules}
    values: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if _is_module_dependency(edge, module_ids):
            values[edge.source_id].add(edge.target_id)
    return {key: tuple(sorted(value)) for key, value in values.items()}


def _is_module_dependency(edge: FactEdge, module_ids: set[str]) -> bool:
    return (
        edge.source_id in module_ids
        and edge.target_id in module_ids
        and edge.kind in {"calls", "imports", "inherits"}
        and edge.rule_id == "aggregate_module_occurrences_v1"
    )


def _tarjan(
    node_ids: tuple[str, ...], adjacency: dict[str, tuple[str, ...]]
) -> tuple[tuple[str, ...], ...]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)
        for target_id in adjacency.get(node_id, ()):
            if target_id not in indices:
                visit(target_id)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target_id])
            elif target_id in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[target_id])
        if lowlinks[node_id] == indices[node_id]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node_id:
                    break
            components.append(tuple(sorted(component)))

    for node_id in sorted(node_ids):
        if node_id not in indices:
            visit(node_id)
    return tuple(sorted(components))


def _layers(modules: tuple[FactNode, ...]) -> tuple[Layer, ...]:
    groups: dict[str, list[FactNode]] = defaultdict(list)
    for module in modules:
        value = f"{module.name}/{module.path or ''}".lower()
        matches: list[str] = []
        rules: list[str] = []
        for kind, needles in (
            ("Tests", ("test", "spec")),
            ("Persistence", ("store", "database", "db", "persistence")),
            ("Infrastructure", ("provider", "adapter", "storage", "indexing")),
            ("Interface/CLI", ("cli", "command", "api")),
            ("Application", ("service", "workflow", "build")),
            ("Domain", ("model", "domain", "parsing", "retrieval")),
        ):
            if any(needle in value for needle in needles):
                matches.append(kind)
                rules.append(f"path_{kind.lower().replace('/', '_')}_v1")
        selected = (
            matches[0] if len(matches) == 1 or matches == ["Tests"] else "unclassified"
        )
        groups[selected].append(module)
    return tuple(
        Layer(
            id=stable_id("layer", kind),
            kind=kind,
            rule_ids=("closed_path_layer_rules_v1",),
            matched_signals=tuple(sorted({item.name for item in members})),
            confidence=1.0 if kind != "unclassified" else 0.0,
            member_node_ids=tuple(sorted(item.id for item in members)),
        )
        for kind, members in sorted(groups.items())
    )


def _edge_counts(
    members: set[str], edges: tuple[FactEdge, ...]
) -> tuple[int, int, int, int]:
    unique_internal: set[tuple[str, str, str]] = set()
    unique_external: set[tuple[str, str, str]] = set()
    internal_occurrences = 0
    external_occurrences = 0
    for edge in edges:
        key = (edge.source_id, edge.target_id, edge.kind)
        if edge.source_id in members and edge.target_id in members:
            unique_internal.add(key)
            internal_occurrences += edge.occurrence_count
        elif edge.source_id in members or edge.target_id in members:
            unique_external.add(key)
            external_occurrences += edge.occurrence_count
    return (
        len(unique_internal),
        len(unique_external),
        internal_occurrences,
        external_occurrences,
    )
