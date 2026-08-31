"""Lift parser occurrences into repository, file, module, and symbol facts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

from repo_dive.errors import RepositoryError
from repo_dive.knowledge_map.models import (
    DerivationParameters,
    FactEdge,
    FactNode,
    stable_id,
)
from repo_dive.knowledge_map.resolution import resolve_python_references
from repo_dive.knowledge_map.snapshot import IndexSnapshot
from repo_dive.parsing.models import Relationship


@dataclass(frozen=True, slots=True)
class LiftedGraph:
    nodes: tuple[FactNode, ...]
    edges: tuple[FactEdge, ...]
    omitted_symbols: int
    omitted_edges: int
    unresolved_references: int
    ambiguous_references: int
    omitted_resolution_candidates: int


def lift_snapshot(
    snapshot: IndexSnapshot,
    parameters: DerivationParameters,
) -> LiftedGraph:
    """Create endpoint-closed facts and deterministic aggregate occurrence edges."""
    repository_id = stable_id("repository", snapshot.source.repository_fingerprint)
    repository = FactNode(
        repository_id,
        "repository",
        "derived",
        "repository",
        None,
        None,
        None,
        None,
        None,
        None,
    )
    modules: dict[str, FactNode] = {}
    files: dict[str, FactNode] = {}
    for file in snapshot.files:
        module_name = _module_name(file.path, file.language)
        module_id = stable_id("module", file.language, module_name)
        modules.setdefault(
            module_id,
            FactNode(
                module_id,
                "module",
                "derived",
                module_name,
                None,
                None,
                None,
                file.language,
                repository_id,
                None,
            ),
        )
        file_id = stable_id("file", file.path)
        files[file.path] = FactNode(
            file_id,
            "file",
            "derived",
            PurePosixPath(file.path).name,
            file.path,
            None,
            None,
            file.language,
            module_id,
            None,
        )
    essential = (
        repository,
        *sorted(modules.values(), key=lambda item: item.id),
        *files.values(),
    )
    if len(essential) > parameters.node_budget:
        raise RepositoryError(
            "knowledge_map_budget_exceeded",
            "Essential Knowledge Map nodes exceed the node budget.",
            details={
                "budget_name": "node_budget",
                "recovery_action": "raise_named_budget",
                "retry_mode": "after_recovery",
            },
        )
    symbol_capacity = parameters.node_budget - len(essential)
    selected_symbols = snapshot.symbols[:symbol_capacity]
    resolution = resolve_python_references(
        snapshot.symbols,
        snapshot.relationships,
        candidate_budget=parameters.resolution_candidates_per_reference,
    )
    resolution_by_reference = {
        item.reference_symbol_id: item for item in resolution.resolutions
    }
    selected_symbol_ids = {item.id for item in selected_symbols}

    def resolution_state(
        symbol_id: str,
    ) -> tuple[str | None, tuple[str, ...], str | None, bool]:
        item = resolution_by_reference.get(symbol_id)
        if item is None:
            return None, (), None, False
        candidates = tuple(
            candidate
            for candidate in item.candidate_symbol_ids
            if candidate in selected_symbol_ids
        )
        candidates_omitted = len(candidates) != len(item.candidate_symbol_ids)
        if item.status == "resolved" and not candidates:
            return "unresolved", (), None, False
        return (
            item.status,
            candidates,
            item.rule_id,
            item.candidates_truncated or candidates_omitted,
        )

    symbols = tuple(
        FactNode(
            item.id,
            "symbol",
            "parser",
            item.qualified_name,
            item.path,
            item.start_line,
            item.end_line,
            files[item.path].language,
            files[item.path].id,
            item.id,
            resolution_status=resolution_state(item.id)[0],
            resolution_candidate_ids=resolution_state(item.id)[1],
            resolution_rule_id=resolution_state(item.id)[2],
            resolution_candidates_truncated=resolution_state(item.id)[3],
        )
        for item in selected_symbols
    )
    nodes = tuple((*essential, *symbols))
    selected_ids = {item.id for item in symbols}
    occurrences = tuple(
        item
        for item in snapshot.relationships
        if item.source_id in selected_ids
        and resolution.resolved_target(item) in selected_ids
    )
    aggregates = _aggregate_edges(
        occurrences,
        resolution,
        files,
        {item.id: item.path for item in selected_symbols},
        parameters.contributing_relationship_ids_per_edge,
    )
    parser_edges = tuple(_parser_edge(item, item.target_id) for item in occurrences)
    resolution_edges = tuple(
        _resolution_edge(item)
        for item in resolution.resolutions
        if item.status == "resolved"
        and item.reference_symbol_id in selected_ids
        and item.resolved_symbol_id in selected_ids
    )
    candidate_edge_count = len(aggregates) + len(resolution_edges) + len(parser_edges)
    if len(resolution_edges) > parameters.edge_budget:
        raise RepositoryError(
            "knowledge_map_budget_exceeded",
            "Required Knowledge Map resolution edges exceed the edge budget.",
            details={
                "budget_name": "edge_budget",
                "provided": parameters.edge_budget,
                "required": len(resolution_edges),
                "recovery_action": "raise_named_budget",
                "retry_mode": "after_recovery",
            },
        )
    remaining_capacity = parameters.edge_budget - len(resolution_edges)
    optional_tiers = (
        tuple(edge for edge in parser_edges if edge.kind == "calls"),
        tuple(edge for edge in parser_edges if edge.kind == "imports"),
        aggregates,
        tuple(edge for edge in parser_edges if edge.kind not in {"calls", "imports"}),
    )
    selected_edges = list(sorted(resolution_edges, key=lambda item: item.id))
    for tier in optional_tiers:
        ordered_tier = sorted(tier, key=lambda item: item.id)
        selected_edges.extend(ordered_tier[:remaining_capacity])
        remaining_capacity -= min(len(ordered_tier), remaining_capacity)
    included_edges = tuple(
        sorted(selected_edges, key=lambda item: (item.origin, item.id))
    )
    unresolved = sum(
        item.status in {"unresolved", "unsupported"} for item in resolution.resolutions
    )
    ambiguous = sum(item.status == "ambiguous" for item in resolution.resolutions)
    return LiftedGraph(
        nodes=nodes,
        edges=included_edges,
        omitted_symbols=len(snapshot.symbols) - len(selected_symbols),
        omitted_edges=candidate_edge_count - len(included_edges),
        unresolved_references=unresolved,
        ambiguous_references=ambiguous,
        omitted_resolution_candidates=sum(
            candidate not in selected_ids
            for item in resolution.resolutions
            for candidate in item.candidate_symbol_ids
        ),
    )


def _parser_edge(relationship: Relationship, target_id: str) -> FactEdge:
    return FactEdge(
        id=f"edge:{relationship.id}",
        source_id=relationship.source_id,
        target_id=target_id,
        kind=relationship.kind,
        origin="parser",
        relationship_id=relationship.id,
        rule_id=None,
        occurrence_count=1,
        unique_source_count=1,
        unique_target_count=1,
        confidence_min=relationship.confidence,
        confidence_max=relationship.confidence,
        contributor_total=1,
        contributing_relationship_ids=(relationship.id,),
        contributors_truncated=False,
        evidence_path=relationship.path,
        evidence_start_line=relationship.start_line,
        evidence_end_line=relationship.end_line,
    )


def _resolution_edge(resolution: object) -> FactEdge:
    from repo_dive.knowledge_map.resolution import ReferenceResolution

    assert isinstance(resolution, ReferenceResolution)
    assert resolution.resolved_symbol_id is not None
    relationship_id = resolution.relationship_id
    return FactEdge(
        id=stable_id(
            "edge",
            "python_reference_resolution_v1",
            resolution.reference_symbol_id,
            resolution.resolved_symbol_id,
            relationship_id,
        ),
        source_id=resolution.reference_symbol_id,
        target_id=resolution.resolved_symbol_id,
        kind="resolves_to",
        origin="derived",
        relationship_id=None,
        rule_id=resolution.rule_id or "python_reference_resolution_v1",
        occurrence_count=1,
        unique_source_count=1,
        unique_target_count=1,
        confidence_min=1.0,
        confidence_max=1.0,
        contributor_total=1,
        contributing_relationship_ids=(relationship_id,),
        contributors_truncated=False,
    )


def _aggregate_edges(
    relationships: tuple[Relationship, ...],
    resolution: object,
    files: dict[str, FactNode],
    symbol_paths: dict[str, str],
    contributor_budget: int,
) -> tuple[FactEdge, ...]:
    from repo_dive.knowledge_map.resolution import ResolutionResult

    resolved = resolution
    assert isinstance(resolved, ResolutionResult)
    groups: dict[tuple[str, str, str, str], list[Relationship]] = defaultdict(list)
    for relationship in relationships:
        source_file = files[relationship.path]
        target_id = resolved.resolved_target(relationship)
        target_path = symbol_paths.get(target_id, relationship.path)
        target_file = files.get(target_path, source_file)
        groups[("file", source_file.id, target_file.id, relationship.kind)].append(
            relationship
        )
        source_module = source_file.parent_id
        target_module = target_file.parent_id
        if source_module is not None and target_module is not None:
            groups[("module", source_module, target_module, relationship.kind)].append(
                relationship
            )
    result: list[FactEdge] = []
    for (level, source_id, target_id, kind), values in sorted(groups.items()):
        ordered = sorted(values, key=lambda item: item.id)
        contributors = tuple(item.id for item in ordered[:contributor_budget])
        result.append(
            FactEdge(
                id=stable_id("edge", "aggregate_v1", level, source_id, target_id, kind),
                source_id=source_id,
                target_id=target_id,
                kind=kind,
                origin="derived",
                relationship_id=None,
                rule_id=f"aggregate_{level}_occurrences_v1",
                occurrence_count=len(ordered),
                unique_source_count=len({item.source_id for item in ordered}),
                unique_target_count=len(
                    {resolved.resolved_target(item) for item in ordered}
                ),
                confidence_min=min(item.confidence for item in ordered),
                confidence_max=max(item.confidence for item in ordered),
                contributor_total=len(ordered),
                contributing_relationship_ids=contributors,
                contributors_truncated=len(contributors) < len(ordered),
            )
        )
    return tuple(result)


def _module_name(path: str, language: str) -> str:
    candidate = PurePosixPath(path)
    without_suffix = candidate.with_suffix("")
    parts = without_suffix.parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    separator = "." if language == "python" else "/"
    return separator.join(parts) or candidate.stem
