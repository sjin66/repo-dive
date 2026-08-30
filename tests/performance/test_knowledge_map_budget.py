from __future__ import annotations

from pathlib import Path

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import IndexService, load_published_index
from repo_dive.knowledge_map.build import KnowledgeMapBuildService
from repo_dive.knowledge_map.evidence_service import KnowledgeMapEvidenceService
from repo_dive.knowledge_map.models import MapBuildBudgets
from repo_dive.knowledge_map.snapshot import snapshot_from_published_index


def test_source_fact_budget_rejects_large_inventory_before_derivation(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    for index in range(50):
        (repository / f"module_{index}.py").write_text(
            f"def function_{index}():\n    return {index}\n", encoding="utf-8"
        )
    IndexService().build(repository)

    with pytest.raises(RepositoryError) as exc_info:
        snapshot_from_published_index(
            load_published_index(repository), source_fact_budget=10
        )

    assert exc_info.value.code == "knowledge_map_source_budget_exceeded"


def test_map_outputs_and_repeated_evidence_remain_within_persisted_bounds(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text(
        "def helper():\n    return 1\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    IndexService().build(repository)
    budgets = _budgets()
    artifact = KnowledgeMapBuildService().build(repository, budgets=budgets).artifact

    assert len(artifact.flows) <= budgets.flow_budget
    assert len(artifact.tour) <= budgets.tour_budget
    artifact_path = repository / ".repo-dive/knowledge-map.json"
    assert len(artifact_path.read_bytes()) <= budgets.artifact_byte_budget

    contract = next(
        item
        for item in artifact.scope_contracts
        if len(item.required_anchor_fact_node_ids)
        <= budgets.evidence_references_per_snapshot
    )
    service = KnowledgeMapEvidenceService()
    first = service.collect(repository, scope_id=contract.scope_id, token_budget=10_000)
    first_bytes = artifact_path.read_bytes()
    replay = service.collect(
        repository, scope_id=contract.scope_id, token_budget=10_000
    )

    assert first.changed is True
    assert len(first.snapshot.references) <= budgets.evidence_references_per_snapshot
    assert replay.changed is False
    assert artifact_path.read_bytes() == first_bytes
    assert len(first_bytes) <= budgets.artifact_byte_budget


def _budgets() -> MapBuildBudgets:
    return MapBuildBudgets(
        source_fact_budget=100,
        artifact_byte_budget=1_000_000,
        node_budget=100,
        edge_budget=100,
        contributing_relationship_ids_per_edge=8,
        resolution_candidates_per_reference=4,
        cluster_budget=10,
        minimum_cluster_files=1,
        flow_budget=1,
        flow_depth=3,
        nodes_per_flow=3,
        edges_per_flow=2,
        tour_budget=1,
        evidence_snapshots=2,
        evidence_references_per_snapshot=1,
        enrichment_records=4,
        records_per_scope=2,
        claims_per_record=2,
        fact_node_ids_per_claim=2,
        related_node_ids_per_claim=2,
        evidence_ids_per_claim=1,
        enrichment_input_bytes=10_000,
    )
