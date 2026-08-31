from __future__ import annotations

from repo_dive.knowledge_map.analysis import analyze_importance
from repo_dive.knowledge_map.models import FactEdge, FactNode


def test_importance_counts_unique_neighbors_not_occurrences() -> None:
    nodes = (
        FactNode("a", "symbol", "parser", "main", "a.py", 1, 1, "python", "f", "a"),
        FactNode("b", "symbol", "parser", "run", "a.py", 2, 2, "python", "f", "b"),
    )
    edges = tuple(_edge(f"r{index}") for index in range(2))

    analyzed = {node.id: node for node in analyze_importance(nodes, edges)}
    source_signals = analyzed["a"].importance_signals
    target_signals = analyzed["b"].importance_signals
    source_rank = analyzed["a"].importance_rank
    assert source_signals is not None
    assert target_signals is not None
    assert source_rank is not None

    assert source_signals.unique_fan_out == 1
    assert target_signals.unique_fan_in == 1
    assert source_signals.entrypoint is True
    assert source_rank.entrypoint == -1


def _edge(relationship_id: str) -> FactEdge:
    return FactEdge(
        f"edge:{relationship_id}",
        "a",
        "b",
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
        "a.py",
        1,
        1,
    )
