from __future__ import annotations

import pytest

from repo_dive.knowledge_map.flows import (
    derive_scope_contracts,
    derive_static_flows,
    derive_tour,
)
from repo_dive.knowledge_map.models import (
    Cluster,
    FactEdge,
    FactNode,
    ImportanceRank,
    ImportanceSignals,
    ScopeContract,
    StaticFlow,
    TourItem,
)


def test_flow_is_cycle_safe_and_tour_does_not_repeat_targets() -> None:
    nodes = (
        _node("main", "main", (-1, "main")),
        _node("run", "run", (0, "run")),
    )
    edges = (_edge("main", "run"), _edge("run", "main"))

    analysis = derive_static_flows(
        nodes,
        edges,
        flow_budget=10,
        flow_depth=5,
        nodes_per_flow=5,
        edges_per_flow=4,
    )
    tour_analysis = derive_tour(nodes, (), analysis.flows, tour_budget=10)
    flows = analysis.flows
    tour = tour_analysis.items

    assert flows[0].terminal_reason == "cycle"
    assert flows[0].step_node_ids == ("main", "run")
    assert flows[0].execution_semantics == "static"
    assert flows[0].representative_relationship_ids == ("main:run",)
    assert analysis.included_count == 1
    assert analysis.omitted_count == 0
    assert len({item.target_id for item in tour}) == len(tour)


def test_flow_analysis_reports_no_roots() -> None:
    analysis = derive_static_flows(
        (_node("run", "run", (0, "run")),),
        (),
        flow_budget=10,
        flow_depth=5,
        nodes_per_flow=5,
        edges_per_flow=4,
    )

    assert analysis.flows == ()
    assert analysis.no_roots is True


def test_branch_order_truncation_and_utility_suppression_are_explicit() -> None:
    nodes = (
        _node("main", "main", (-1, "main")),
        _node("alpha", "alpha", (0, "alpha")),
        _node("beta", "beta", (0, "beta")),
        _node("identity", "identity", (0, "identity")),
    )
    edges = (
        _edge("main", "beta"),
        _edge("main", "alpha"),
        _edge("main", "identity"),
    )

    analysis = derive_static_flows(
        nodes,
        edges,
        flow_budget=10,
        flow_depth=5,
        nodes_per_flow=2,
        edges_per_flow=1,
    )

    assert tuple(flow.step_node_ids for flow in analysis.flows) == (
        ("main", "alpha"),
        ("main", "beta"),
        ("main", "identity"),
    )
    assert all(flow.truncated for flow in analysis.flows)
    assert all(flow.terminal_reason == "size_limit" for flow in analysis.flows)

    utility_analysis = derive_static_flows(
        nodes,
        (_edge("main", "identity"),),
        flow_budget=10,
        flow_depth=5,
        nodes_per_flow=5,
        edges_per_flow=5,
    )
    assert len(utility_analysis.flows) == 1
    assert utility_analysis.flows[0].terminal_reason == "utility_suppressed"
    assert utility_analysis.flows[0].step_node_ids == ("main",)
    assert utility_analysis.flows[0].suppressed_utility_node_ids == ("identity",)
    assert utility_analysis.truncation_reasons == ("utility_suppressed",)


@pytest.mark.parametrize(
    ("root_count", "expected_omitted", "expected_reasons"),
    (
        (4, 3, ("flow_budget",)),
        (5, 4, ("candidate_budget", "flow_budget")),
        (6, 5, ("candidate_budget", "flow_budget")),
    ),
)
def test_candidate_budget_counts_unstarted_roots_once(
    root_count: int,
    expected_omitted: int,
    expected_reasons: tuple[str, ...],
) -> None:
    nodes = tuple(
        _node(f"root-{index}", f"pkg{index}.main", (index, f"root-{index}"))
        for index in range(root_count)
    )

    analysis = derive_static_flows(
        nodes,
        (),
        flow_budget=1,
        flow_depth=3,
        nodes_per_flow=1,
        edges_per_flow=1,
    )

    assert tuple(flow.root_node_id for flow in analysis.flows) == ("root-0",)
    assert analysis.included_count == 1
    assert analysis.omitted_count == expected_omitted
    assert analysis.truncation_reasons == expected_reasons


def test_candidate_budget_counts_branched_frontier_and_unstarted_roots_once() -> None:
    roots = tuple(
        _node(f"root-{index}", f"pkg{index}.main", (index, f"root-{index}"))
        for index in range(3)
    )
    leaves = tuple(
        _node(f"leaf-{index}", f"leaf{index}", (10 + index, f"leaf-{index}"))
        for index in range(8)
    )
    edges = tuple(_edge("root-0", leaf.id) for leaf in leaves)

    analysis = derive_static_flows(
        (*roots, *leaves),
        edges,
        flow_budget=1,
        flow_depth=3,
        nodes_per_flow=2,
        edges_per_flow=1,
    )

    assert tuple(flow.step_node_ids for flow in analysis.flows) == (
        ("root-0", "leaf-0"),
    )
    assert analysis.included_count == 1
    assert analysis.omitted_count == 9
    assert analysis.truncation_reasons == ("candidate_budget", "flow_budget")


def test_scope_contracts_close_ancestors_anchors_permissions_and_hashes() -> None:
    nodes = (
        FactNode(
            "repo", "repository", "derived", "repo", None, None, None, None, None, None
        ),
        FactNode(
            "m1", "module", "derived", "m1", None, None, None, "python", "repo", None
        ),
        FactNode(
            "m2", "module", "derived", "m2", None, None, None, "python", "repo", None
        ),
        FactNode(
            "f1", "file", "derived", "a.py", "a.py", None, None, "python", "m1", None
        ),
        FactNode(
            "f2", "file", "derived", "b.py", "b.py", None, None, "python", "m2", None
        ),
        FactNode(
            "s1", "symbol", "parser", "a.main", "a.py", 1, 1, "python", "f1", "s1"
        ),
        FactNode("s2", "symbol", "parser", "b.run", "b.py", 1, 1, "python", "f2", "s2"),
    )
    cluster = Cluster(
        "cluster", ("f1",), ("package_directory_boundary_v1",), 0, 0, 0, 0
    )
    flow = StaticFlow(
        "flow",
        "s1",
        ("s1", "s2"),
        ("edge",),
        ("calls",),
        "terminal",
        1.0,
        False,
        False,
        transition_semantics=("runtime_call",),
        representative_relationship_ids=("relationship",),
    )
    tour = TourItem("tour", "cluster", "cluster", None, (1, "cluster"), None)

    contracts = derive_scope_contracts(nodes, (cluster,), (flow,), (tour,))
    by_id = {contract.scope_id: contract for contract in contracts}

    assert by_id["cluster"].allowed_fact_node_ids == ("s1", "f1", "m1", "repo")
    assert by_id["cluster"].required_anchor_fact_node_ids == ("f1",)
    assert by_id["flow"].allowed_fact_node_ids == (
        "s1",
        "f1",
        "m1",
        "repo",
        "s2",
        "f2",
        "m2",
    )
    assert by_id["flow"].required_anchor_fact_node_ids == ("s1", "s2")
    assert ScopeContract.from_document(by_id["tour"].to_document()) == by_id["tour"]
    assert by_id["tour"].allowed_record_kinds == ("reading_guidance", "concept")
    assert set(by_id["tour"].required_anchor_fact_node_ids) <= set(
        by_id["tour"].allowed_fact_node_ids
    )


def _node(node_id: str, name: str, rank: tuple[int | str, ...]) -> FactNode:
    return FactNode(
        node_id,
        "symbol",
        "parser",
        name,
        "app.py",
        1,
        1,
        "python",
        "file",
        node_id,
        ImportanceSignals(0, 0, False, name == "main", True, 0, 0),
        ImportanceRank(int(rank[0]), 0, 0, 0, 0, "app.py", node_id),
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
