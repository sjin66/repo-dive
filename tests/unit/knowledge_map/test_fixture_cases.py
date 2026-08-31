from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from repo_dive.knowledge_map.flows import derive_static_flows
from repo_dive.knowledge_map.lifting import lift_snapshot
from repo_dive.knowledge_map.models import (
    FactEdge,
    FactNode,
    ImportanceRank,
    ImportanceSignals,
    LanguageCoverage,
    MapCoverage,
    MapSource,
)
from repo_dive.knowledge_map.resolution import resolve_python_references
from repo_dive.knowledge_map.snapshot import IndexSnapshot
from repo_dive.parsing.models import create_relationship, create_symbol
from repo_dive.scanner.models import FileRecord, ReadStatus

from .test_lifting import budgets

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "knowledge_map"


def _cases(name: str) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], json.loads((_FIXTURES / name).read_text()))


@pytest.mark.parametrize("case", _cases("resolution_cases.json"))
def test_resolution_fixture(case: dict[str, Any]) -> None:
    source_path = cast(str, case["source_path"])
    source = create_symbol(
        kind="function",
        name="main",
        qualified_name="app.main",
        path=source_path,
        start_line=1,
        end_line=2,
    )
    reference = create_symbol(
        kind=cast(str, case["reference_kind"]),
        name=cast(str, case["reference_name"]),
        qualified_name=cast(str, case["reference_qualified_name"]),
        path=source_path,
        start_line=2,
        end_line=2,
    )
    candidates = tuple(
        create_symbol(
            kind="function",
            name=cast(str, candidate["qualified_name"]).rsplit(".", 1)[-1],
            qualified_name=cast(str, candidate["qualified_name"]),
            path=cast(str, candidate["path"]),
            start_line=1,
            end_line=1,
        )
        for candidate in cast(list[dict[str, object]], case["candidates"])
    )
    relationship = create_relationship(
        source_id=source.id,
        target_id=reference.id,
        kind="calls",
        confidence=0.75,
        provenance="python_ast",
        path=source_path,
        start_line=2,
        end_line=2,
        occurrence_discriminator=(1, 4, 0),
    )

    resolution = resolve_python_references(
        (*candidates, source, reference),
        (relationship,),
        candidate_budget=cast(int, case["candidate_budget"]),
    ).resolutions[0]

    assert resolution.status == case["expected_status"]
    assert (resolution.resolved_symbol_id is not None) == (
        case["expected_status"] == "resolved"
    )
    assert len(resolution.candidate_symbol_ids) == case["expected_candidate_count"]
    assert resolution.candidates_truncated is case["expected_truncated"]


@pytest.mark.parametrize("case", _cases("lifting_cases.json"))
def test_lifting_fixture(case: dict[str, Any]) -> None:
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
        for index in range(cast(int, case["occurrences"]))
    )
    snapshot = IndexSnapshot(
        MapSource("fingerprint", "build", 5, "non_git", None, None),
        (FileRecord("app.py", "python", 1, "hash", "utf-8", ReadStatus.READ, None),),
        (module, function),
        relationships,
        MapCoverage(
            total_files=1,
            indexed_files=1,
            symbols=2,
            relationship_occurrences=cast(int, case["occurrences"]),
            languages=(("python", 1),),
            relationship_kinds=(("contains", cast(int, case["occurrences"])),),
            parser_coverage=(
                LanguageCoverage(
                    "python",
                    1,
                    1,
                    2,
                    cast(int, case["occurrences"]),
                    (("contains", cast(int, case["occurrences"])),),
                    "full",
                ),
            ),
        ),
    )

    result = lift_snapshot(snapshot, budgets().derivation_parameters())
    parser_edges = tuple(edge for edge in result.edges if edge.origin == "parser")
    aggregate = next(
        edge
        for edge in result.edges
        if edge.origin == "derived" and edge.kind == "contains"
    )

    assert len(parser_edges) == case["expected_parser_edges"]
    assert aggregate.occurrence_count == case["expected_aggregate_occurrences"]
    assert aggregate.unique_source_count == case["expected_unique_sources"]


@pytest.mark.parametrize("case", _cases("flow_cases.json"))
def test_flow_fixture(case: dict[str, Any]) -> None:
    root = cast(str, case["root"])
    nodes = tuple(_node(node_id, node_id == root) for node_id in case["nodes"])
    edges = tuple(_edge(source, target) for source, target in case["edges"])

    flow = derive_static_flows(
        nodes,
        edges,
        flow_budget=10,
        flow_depth=5,
        nodes_per_flow=5,
        edges_per_flow=5,
    ).flows[0]

    assert list(flow.step_node_ids) == case["expected_steps"]
    assert flow.terminal_reason == case["expected_terminal_reason"]


def _node(node_id: str, entrypoint: bool) -> FactNode:
    return FactNode(
        node_id,
        "symbol",
        "parser",
        node_id,
        "app.py",
        1,
        1,
        "python",
        "file",
        node_id,
        ImportanceSignals(0, 0, False, entrypoint, True, 0, 0),
        ImportanceRank(-1 if entrypoint else 0, 0, 0, 0, 0, "app.py", node_id),
    )


def _edge(source: str, target: str) -> FactEdge:
    relationship_id = f"{source}:{target}"
    return FactEdge(
        f"edge:{relationship_id}",
        source,
        target,
        "calls",
        "parser",
        relationship_id,
        None,
        1,
        1,
        1,
        1.0,
        1.0,
        1,
        (relationship_id,),
        False,
        "app.py",
        1,
        1,
    )
