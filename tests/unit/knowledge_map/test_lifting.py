from __future__ import annotations

from dataclasses import replace

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.knowledge_map.flows import derive_static_flows
from repo_dive.knowledge_map.lifting import lift_snapshot
from repo_dive.knowledge_map.models import (
    LanguageCoverage,
    MapBuildBudgets,
    MapCoverage,
    MapSource,
)
from repo_dive.knowledge_map.snapshot import IndexSnapshot
from repo_dive.parsing.models import create_relationship, create_symbol
from repo_dive.scanner.models import FileRecord, ReadStatus


def budgets() -> MapBuildBudgets:
    return MapBuildBudgets(
        100,
        100_000,
        100,
        100,
        8,
        4,
        20,
        1,
        20,
        5,
        20,
        20,
        20,
        20,
        20,
        20,
        10,
        10,
        10,
        10,
        10,
        10_000,
    )


def test_lifting_keeps_occurrences_separate_and_aggregates_counts() -> None:
    module = create_symbol(
        kind="module",
        name="app",
        qualified_name="app",
        path="app.py",
        start_line=1,
        end_line=2,
    )
    function = create_symbol(
        kind="function",
        name="main",
        qualified_name="app.main",
        path="app.py",
        start_line=1,
        end_line=2,
    )
    relationships = tuple(
        create_relationship(
            source_id=module.id,
            target_id=function.id,
            kind="contains",
            confidence=1.0,
            provenance="python_ast",
            path="app.py",
            start_line=1,
            end_line=2,
            occurrence_discriminator=(0, 1, index),
        )
        for index in range(2)
    )
    snapshot = IndexSnapshot(
        source=MapSource("fingerprint", "build", 5, "non_git", None, None),
        files=(
            FileRecord("app.py", "python", 1, "hash", "utf-8", ReadStatus.READ, None),
        ),
        symbols=(module, function),
        relationships=relationships,
        coverage=MapCoverage(
            total_files=1,
            indexed_files=1,
            symbols=2,
            relationship_occurrences=2,
            languages=(("python", 1),),
            relationship_kinds=(("contains", 2),),
            parser_coverage=(
                LanguageCoverage("python", 1, 1, 2, 2, (("contains", 2),), "full"),
            ),
        ),
    )

    lifted = lift_snapshot(snapshot, budgets().derivation_parameters())
    parser_edges = tuple(edge for edge in lifted.edges if edge.origin == "parser")
    aggregate = tuple(
        edge
        for edge in lifted.edges
        if edge.kind == "contains" and edge.origin == "derived"
    )

    assert len(parser_edges) == 2
    assert aggregate[0].occurrence_count == 2
    assert aggregate[0].unique_source_count == 1

    constrained = lift_snapshot(
        snapshot,
        replace(budgets().derivation_parameters(), edge_budget=1),
    )
    assert constrained.edges == (min(aggregate, key=lambda edge: edge.id),)
    assert constrained.omitted_edges == 3


def test_lifting_persists_ambiguous_resolution_without_choosing_winner() -> None:
    source = create_symbol(
        kind="function",
        name="main",
        qualified_name="app.main",
        path="app.py",
        start_line=1,
        end_line=2,
    )
    reference = create_symbol(
        kind="reference",
        name="run",
        qualified_name="run",
        path="app.py",
        start_line=2,
        end_line=2,
    )
    candidates = tuple(
        create_symbol(
            kind="function",
            name="run",
            qualified_name=f"pkg{index}.run",
            path=f"pkg{index}.py",
            start_line=1,
            end_line=1,
        )
        for index in range(2)
    )
    relationship = create_relationship(
        source_id=source.id,
        target_id=reference.id,
        kind="calls",
        confidence=0.75,
        provenance="python_ast",
        path="app.py",
        start_line=2,
        end_line=2,
        occurrence_discriminator=(1, 4, 0),
    )
    files = tuple(
        FileRecord(path, "python", 1, "hash", "utf-8", ReadStatus.READ, None)
        for path in ("app.py", "pkg0.py", "pkg1.py")
    )
    snapshot = IndexSnapshot(
        source=MapSource("fingerprint", "build", 5, "non_git", None, None),
        files=files,
        symbols=(*candidates, source, reference),
        relationships=(relationship,),
        coverage=MapCoverage(
            total_files=3,
            indexed_files=3,
            symbols=4,
            relationship_occurrences=1,
            languages=(("python", 3),),
            relationship_kinds=(("calls", 1),),
            parser_coverage=(
                LanguageCoverage("python", 3, 3, 4, 1, (("calls", 1),), "full"),
            ),
        ),
    )

    lifted = lift_snapshot(snapshot, budgets().derivation_parameters())
    reference_node = next(node for node in lifted.nodes if node.id == reference.id)

    assert reference_node.resolution_status == "ambiguous"
    assert reference_node.resolution_candidate_ids == tuple(
        candidate.id for candidate in candidates
    )
    assert reference_node.resolution_rule_id == "python_ambiguous_v1"
    assert reference_node.resolution_candidates_truncated is False
    assert not any(edge.kind == "resolves_to" for edge in lifted.edges)


def test_lifting_rejects_edge_budget_below_mandatory_resolution_closure() -> None:
    snapshot = _resolved_snapshot(("calls", "imports"))
    parameters = replace(budgets().derivation_parameters(), edge_budget=1)

    with pytest.raises(RepositoryError) as raised:
        lift_snapshot(snapshot, parameters)

    assert raised.value.code == "knowledge_map_budget_exceeded"
    assert raised.value.details == {
        "budget_name": "edge_budget",
        "provided": 1,
        "required": 2,
        "recovery_action": "raise_named_budget",
        "retry_mode": "after_recovery",
    }


@pytest.mark.parametrize("relationship_kind", ["calls", "imports"])
def test_lifting_prioritizes_flow_edges_after_mandatory_resolution_closure(
    relationship_kind: str,
) -> None:
    snapshot = _resolved_snapshot((relationship_kind,))
    parameters = replace(budgets().derivation_parameters(), edge_budget=2)

    lifted = lift_snapshot(snapshot, parameters)

    assert tuple((edge.origin, edge.kind) for edge in lifted.edges) == (
        ("derived", "resolves_to"),
        ("parser", relationship_kind),
    )
    assert lifted.omitted_edges == 2
    assert lifted.edges == tuple(
        sorted(lifted.edges, key=lambda edge: (edge.origin, edge.id))
    )
    flow = derive_static_flows(
        lifted.nodes,
        lifted.edges,
        flow_budget=1,
        flow_depth=5,
        nodes_per_flow=5,
        edges_per_flow=5,
    ).flows[0]
    parser_edge = next(edge for edge in lifted.edges if edge.origin == "parser")
    assert flow.step_node_ids == (parser_edge.source_id, parser_edge.target_id)
    assert flow.representative_relationship_ids == (parser_edge.relationship_id,)


def test_lifting_prioritizes_calls_before_imports() -> None:
    snapshot = _resolved_snapshot(("imports", "calls"))
    parameters = replace(budgets().derivation_parameters(), edge_budget=3)

    lifted = lift_snapshot(snapshot, parameters)

    retained_parser_edges = tuple(
        edge for edge in lifted.edges if edge.origin == "parser"
    )
    assert tuple(edge.kind for edge in retained_parser_edges) == ("calls",)


def test_lifting_selects_flow_edges_by_stable_id_within_a_tier() -> None:
    snapshot = _resolved_snapshot(("calls", "calls"))
    parameters = replace(budgets().derivation_parameters(), edge_budget=3)

    lifted = lift_snapshot(snapshot, parameters)

    retained_call = next(
        edge
        for edge in lifted.edges
        if edge.origin == "parser" and edge.kind == "calls"
    )
    assert retained_call.id == min(
        f"edge:{relationship.id}" for relationship in snapshot.relationships
    )


def test_lifting_exact_resolution_boundary_preserves_required_closure() -> None:
    snapshot = _resolved_snapshot(("calls", "imports"))
    parameters = replace(budgets().derivation_parameters(), edge_budget=2)

    lifted = lift_snapshot(snapshot, parameters)
    resolved_nodes = tuple(
        node for node in lifted.nodes if node.resolution_status == "resolved"
    )

    assert len(resolved_nodes) == 2
    assert {edge.source_id for edge in lifted.edges if edge.kind == "resolves_to"} == {
        node.id for node in resolved_nodes
    }
    assert lifted.omitted_edges == 6


def _resolved_snapshot(relationship_kinds: tuple[str, ...]) -> IndexSnapshot:
    source = create_symbol(
        kind="function",
        name="main",
        qualified_name="app.main",
        path="app.py",
        start_line=1,
        end_line=4,
    )
    candidate = create_symbol(
        kind="function",
        name="run",
        qualified_name="helper.run",
        path="helper.py",
        start_line=1,
        end_line=1,
    )
    references = tuple(
        create_symbol(
            kind="reference" if kind == "calls" else "import",
            name="run",
            qualified_name="helper.run",
            path="app.py",
            start_line=index + 2,
            end_line=index + 2,
        )
        for index, kind in enumerate(relationship_kinds)
    )
    relationships = tuple(
        create_relationship(
            source_id=source.id,
            target_id=reference.id,
            kind=kind,
            confidence=0.75,
            provenance="python_ast",
            path="app.py",
            start_line=index + 2,
            end_line=index + 2,
            occurrence_discriminator=(index + 1, 0, 0),
        )
        for index, (kind, reference) in enumerate(
            zip(relationship_kinds, references, strict=True)
        )
    )
    kind_counts = tuple(
        (kind, relationship_kinds.count(kind))
        for kind in sorted(set(relationship_kinds))
    )
    return IndexSnapshot(
        source=MapSource("fingerprint", "build", 5, "non_git", None, None),
        files=(
            FileRecord(
                "app.py", "python", 4, "app-hash", "utf-8", ReadStatus.READ, None
            ),
            FileRecord(
                "helper.py", "python", 1, "helper-hash", "utf-8", ReadStatus.READ, None
            ),
        ),
        symbols=(candidate, source, *references),
        relationships=relationships,
        coverage=MapCoverage(
            total_files=2,
            indexed_files=2,
            symbols=2 + len(references),
            relationship_occurrences=len(relationships),
            languages=(("python", 2),),
            relationship_kinds=kind_counts,
            parser_coverage=(
                LanguageCoverage(
                    "python",
                    2,
                    2,
                    2 + len(references),
                    len(relationships),
                    kind_counts,
                    "full",
                ),
            ),
        ),
    )
