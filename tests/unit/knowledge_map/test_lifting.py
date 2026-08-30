from __future__ import annotations

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
