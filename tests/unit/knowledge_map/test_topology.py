from __future__ import annotations

from repo_dive.knowledge_map.models import FactEdge, FactNode
from repo_dive.knowledge_map.topology import derive_topology


def test_topology_reports_module_cycle_without_rewriting_edges() -> None:
    nodes = (
        _node("repo", "repository", "repo", None, None),
        _node("m1", "module", "service", None, "repo"),
        _node("m2", "module", "store", None, "repo"),
        _node("f1", "file", "a.py", "a.py", "m1"),
        _node("f2", "file", "b.py", "b.py", "m2"),
    )
    edges = (_edge("m1", "m2"), _edge("m2", "m1"))

    topology = derive_topology(nodes, edges, cluster_budget=10, minimum_cluster_files=1)

    assert ("m1", "m2") in topology.strongly_connected_components
    assert topology.cycle_groups[0].member_module_ids == ("m1", "m2")
    assert all(
        scc_id in {group.id for group in topology.cycle_groups}
        for cluster in topology.clusters
        for scc_id in cluster.scc_ids
    )
    assert {layer.kind for layer in topology.layers} == {"Application", "Persistence"}


def test_undersized_directory_merges_by_maximum_connectivity() -> None:
    nodes = (
        _node("repo", "repository", "repo", None, None),
        _node("module", "module", "domain", None, "repo"),
        *(
            _node(node_id, "file", path.rsplit("/", 1)[-1], path, "module")
            for node_id, path in (
                ("core1", "core/a.py"),
                ("core2", "core/b.py"),
                ("aux", "aux/a.py"),
                ("other1", "other/a.py"),
                ("other2", "other/b.py"),
            )
        ),
    )
    edges = (
        _edge("aux", "core1"),
        _edge("aux", "other1"),
        _edge("aux", "other2"),
    )

    topology = derive_topology(nodes, edges, cluster_budget=10, minimum_cluster_files=2)
    merged = next(
        cluster for cluster in topology.clusters if "aux" in cluster.member_node_ids
    )

    assert set(merged.member_node_ids) == {"aux", "other1", "other2"}
    assert merged.formation_signals == ("maximum_connectivity_undersized_merge_v1",)


def test_module_self_loop_is_persisted_as_cycle_group() -> None:
    nodes = (
        _node("repo", "repository", "repo", None, None),
        _node("module", "module", "service", None, "repo"),
        _node("file", "file", "service.py", "service.py", "module"),
    )

    topology = derive_topology(
        nodes, (_edge("module", "module"),), cluster_budget=10, minimum_cluster_files=1
    )

    assert topology.cycle_groups[0].member_module_ids == ("module",)
    assert topology.cycle_groups[0].edge_ids == ("edge:module:module",)


def _node(
    node_id: str,
    kind: str,
    name: str,
    path: str | None,
    parent_id: str | None,
) -> FactNode:
    return FactNode(
        node_id,
        kind,  # type: ignore[arg-type]
        "derived",
        name,
        path,
        None,
        None,
        "python" if kind != "repository" else None,
        parent_id,
        None,
    )


def _edge(source: str, target: str) -> FactEdge:
    relationship_id = f"{source}:{target}"
    return FactEdge(
        f"edge:{relationship_id}",
        source,
        target,
        "imports",
        "derived",
        None,
        "aggregate_module_occurrences_v1",
        1,
        1,
        1,
        1.0,
        1.0,
        1,
        (relationship_id,),
        False,
    )
