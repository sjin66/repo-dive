from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.knowledge_map.models import (
    KnowledgeMapArtifact,
    MapBuildBudgets,
    MapSource,
)
from repo_dive.knowledge_map.store import MapStore


def budgets() -> MapBuildBudgets:
    values = {
        "source_fact_budget": 100,
        "artifact_byte_budget": 100_000,
        "node_budget": 100,
        "edge_budget": 100,
        "contributing_relationship_ids_per_edge": 8,
        "resolution_candidates_per_reference": 4,
        "cluster_budget": 20,
        "minimum_cluster_files": 1,
        "flow_budget": 20,
        "flow_depth": 5,
        "nodes_per_flow": 20,
        "edges_per_flow": 20,
        "tour_budget": 20,
        "evidence_snapshots": 20,
        "evidence_references_per_snapshot": 20,
        "enrichment_records": 20,
        "records_per_scope": 10,
        "claims_per_record": 10,
        "fact_node_ids_per_claim": 10,
        "related_node_ids_per_claim": 10,
        "evidence_ids_per_claim": 10,
        "enrichment_input_bytes": 10_000,
    }
    return MapBuildBudgets(**cast(Any, values))


def artifact(value: MapBuildBudgets | None = None) -> KnowledgeMapArtifact:
    return KnowledgeMapArtifact.create_empty(
        source=MapSource("fingerprint", "build", 5, "non_git", None, None),
        budgets=value or budgets(),
    )


def test_transaction_writes_and_reads_one_strict_artifact(tmp_path: Path) -> None:
    store = MapStore(tmp_path)
    baseline = store.read_snapshot()

    with store.write_transaction(baseline, lock_timeout=0.2) as transaction:
        result = transaction.commit(artifact())

    assert result.changed is True
    assert store.read_snapshot().artifact == artifact()


def test_transaction_detects_non_equivalent_baseline_change(tmp_path: Path) -> None:
    store = MapStore(tmp_path)
    absent = store.read_snapshot()
    with store.write_transaction(absent) as transaction:
        transaction.commit(artifact())

    with (
        store.write_transaction(absent) as transaction,
        pytest.raises(RepositoryError) as exc_info,
    ):
        transaction.commit(artifact(), equivalent=lambda _current: False)

    assert exc_info.value.code == "knowledge_map_revision_conflict"


def test_equivalence_runs_before_cas_and_returns_unchanged(tmp_path: Path) -> None:
    store = MapStore(tmp_path)
    absent = store.read_snapshot()
    current = artifact()
    with store.write_transaction(absent) as transaction:
        transaction.commit(current)

    candidate = KnowledgeMapArtifact.create_empty(
        source=current.source,
        budgets=replace(budgets(), artifact_byte_budget=200_000),
    )
    with store.write_transaction(absent) as transaction:
        result = transaction.commit(
            candidate, equivalent=lambda value: value == current
        )

    assert result.changed is False
    assert store.read_snapshot().artifact == current


def test_transaction_rejects_non_monotonic_candidate_revision(tmp_path: Path) -> None:
    store = MapStore(tmp_path)
    baseline = store.read_snapshot()
    current = artifact()
    with store.write_transaction(baseline) as transaction:
        transaction.commit(current)
    previous_bytes = (tmp_path / ".repo-dive/knowledge-map.json").read_bytes()

    current_snapshot = store.read_snapshot()
    with (
        store.write_transaction(current_snapshot) as transaction,
        pytest.raises(RepositoryError) as exc_info,
    ):
        transaction.commit(current)

    assert exc_info.value.code == "knowledge_map_validation_failed"
    assert (tmp_path / ".repo-dive/knowledge-map.json").read_bytes() == previous_bytes


def test_under_lock_revalidation_failure_releases_the_writer_lock(
    tmp_path: Path,
) -> None:
    store = MapStore(tmp_path)
    baseline = store.read_snapshot()

    def fail_revalidation() -> None:
        raise RepositoryError("knowledge_map_index_changed", "changed")

    with (
        pytest.raises(RepositoryError),
        store.write_transaction(
            baseline,
            lock_timeout=0.05,
            revalidate=fail_revalidation,
        ),
    ):
        pass

    with store.write_transaction(baseline, lock_timeout=0.05) as transaction:
        result = transaction.commit(artifact())

    assert result.changed is True


def test_atomic_publish_failure_preserves_previous_valid_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MapStore(tmp_path)
    baseline = store.read_snapshot()
    current = artifact()
    with store.write_transaction(baseline) as transaction:
        transaction.commit(current)
    artifact_path = tmp_path / ".repo-dive/knowledge-map.json"
    previous_bytes = artifact_path.read_bytes()
    candidate = KnowledgeMapArtifact.create(
        artifact_revision=2,
        source=current.source,
        derivation_parameters=current.derivation_parameters,
        capacity_limits=current.capacity_limits,
        coverage=current.coverage,
        nodes=current.nodes,
        edges=current.edges,
        cycle_groups=current.cycle_groups,
        clusters=current.clusters,
        layers=current.layers,
        flows=current.flows,
        tour=current.tour,
        scope_contracts=current.scope_contracts,
    )

    def fail_write(*_args: object, **_kwargs: object) -> None:
        raise InternalOperationError("atomic_write_failed", "failed")

    monkeypatch.setattr(
        "repo_dive.knowledge_map.store.atomic_write_bytes",
        fail_write,
    )
    with (
        store.write_transaction(store.read_snapshot()) as transaction,
        pytest.raises(InternalOperationError) as exc_info,
    ):
        transaction.commit(candidate)

    assert exc_info.value.code == "knowledge_map_write_failed"
    assert artifact_path.read_bytes() == previous_bytes
