from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from typing import Protocol, TypeVar

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import IndexService
from repo_dive.knowledge_map.build import KnowledgeMapBuildService
from repo_dive.knowledge_map.enrichment_service import KnowledgeMapEnrichmentService
from repo_dive.knowledge_map.evidence_service import KnowledgeMapEvidenceService
from repo_dive.knowledge_map.models import (
    KnowledgeMapArtifact,
    MapBuildBudgets,
    MapSource,
)
from repo_dive.knowledge_map.store import MapStore


class _ChangedResult(Protocol):
    @property
    def changed(self) -> bool: ...

    @property
    def artifact(self) -> KnowledgeMapArtifact: ...


_ResultT = TypeVar("_ResultT", bound=_ChangedResult)


def test_contested_writer_times_out_without_changing_previous_bytes(
    tmp_path: Path,
) -> None:
    store = MapStore(tmp_path)
    baseline = store.read_snapshot()
    candidate = KnowledgeMapArtifact.create_empty(
        source=MapSource("fingerprint", "build", 5, "non_git", None, None),
        budgets=_budgets(),
    )

    with store.write_transaction(baseline, lock_timeout=0.2) as first:
        with (
            pytest.raises(RepositoryError) as exc_info,
            store.write_transaction(baseline, lock_timeout=0.03),
        ):
            pass
        assert store.read_snapshot().state == "absent"
        first.commit(candidate)

    assert exc_info.value.code == "knowledge_map_locked"
    assert store.read_artifact() == candidate


def test_lock_contention_is_enforced_across_processes(tmp_path: Path) -> None:
    store = MapStore(tmp_path)
    snapshot = store.read_snapshot()
    script = """
import sys
from repo_dive.errors import RepositoryError
from repo_dive.knowledge_map.store import MapStore

store = MapStore(sys.argv[1])
try:
    with store.write_transaction(store.read_snapshot(), lock_timeout=0.05):
        pass
except RepositoryError as error:
    print(error.code)
"""

    with store.write_transaction(snapshot, lock_timeout=0.2):
        completed = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

    assert completed.stdout.strip() == "knowledge_map_locked"
    with store.write_transaction(store.read_snapshot(), lock_timeout=0.2):
        pass


def test_build_and_reset_share_cas_with_equivalence_before_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    IndexService().build(repository)
    build_service = KnowledgeMapBuildService()
    initial = build_service.build(repository, budgets=_budgets()).artifact
    assert initial.scope_contracts
    scope = initial.scope_contracts[0]
    evidence = KnowledgeMapEvidenceService().collect(
        repository, scope_id=scope.scope_id, token_budget=10_000
    )
    payload = json.dumps(
        {
            "schema_version": "1.0",
            "scope_id": scope.scope_id,
            "expected_artifact_revision": evidence.artifact.artifact_revision,
            "records": [
                {
                    "id": f"{scope.allowed_record_kinds[0]}:race",
                    "kind": scope.allowed_record_kinds[0],
                    "claims": [
                        {
                            "kind": "summary",
                            "text": "A coordinated semantic update.",
                            "fact_node_ids": [scope.allowed_fact_node_ids[0]],
                            "related_node_ids": [],
                            "evidence_ids": [
                                evidence.snapshot.references[0].evidence_id
                            ],
                        }
                    ],
                }
            ],
        }
    ).encode()
    initial = (
        KnowledgeMapEnrichmentService().enrich(repository, payload=payload).artifact
    )
    before = (repository / ".repo-dive/knowledge-map.json").read_bytes()

    rendezvous = Barrier(2)
    original = MapStore.write_transaction

    def coordinated_write_transaction(
        self: MapStore, *args: object, **kwargs: object
    ) -> object:
        rendezvous.wait()
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(MapStore, "write_transaction", coordinated_write_transaction)
    larger = replace(_budgets(), artifact_byte_budget=200_000)
    with ThreadPoolExecutor(max_workers=2) as executor:
        build_future = executor.submit(build_service.build, repository, budgets=larger)
        reset_future = executor.submit(
            KnowledgeMapEnrichmentService().reset,
            repository,
            scope_id=scope.scope_id,
        )
        outcomes = (_outcome(build_future), _outcome(reset_future))

    persisted = MapStore(repository).read_artifact()
    successes = [item for item in outcomes if not isinstance(item, RepositoryError)]
    conflicts = [item for item in outcomes if isinstance(item, RepositoryError)]
    assert len(successes) == len(conflicts) == 1
    assert successes[0].changed is True
    assert conflicts[0].code == "knowledge_map_revision_conflict"
    assert persisted == successes[0].artifact
    assert persisted.artifact_revision == initial.artifact_revision + 1
    if persisted.capacity_limits.artifact_byte_budget == 200_000:
        assert persisted.evidence_snapshots == initial.evidence_snapshots
        assert persisted.enrichments == initial.enrichments
    else:
        assert persisted.capacity_limits.artifact_byte_budget == 100_000
        assert not persisted.evidence_snapshots
        assert not persisted.enrichments
    assert (repository / ".repo-dive/knowledge-map.json").read_bytes() != before


def test_build_and_evidence_share_one_cas_without_losing_the_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    IndexService().build(repository)
    build_service = KnowledgeMapBuildService()
    initial = build_service.build(repository, budgets=_budgets()).artifact
    scope_id = initial.scope_contracts[0].scope_id

    rendezvous = Barrier(2)
    original = MapStore.write_transaction

    def coordinated_write_transaction(
        self: MapStore, *args: object, **kwargs: object
    ) -> object:
        rendezvous.wait()
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(MapStore, "write_transaction", coordinated_write_transaction)
    with ThreadPoolExecutor(max_workers=2) as executor:
        build_future = executor.submit(
            build_service.build,
            repository,
            budgets=replace(_budgets(), artifact_byte_budget=200_000),
        )
        evidence_future = executor.submit(
            KnowledgeMapEvidenceService().collect,
            repository,
            scope_id=scope_id,
            token_budget=10_000,
        )
        outcomes = (_outcome(build_future), _outcome(evidence_future))

    persisted = MapStore(repository).read_artifact()
    successes = [item for item in outcomes if not isinstance(item, RepositoryError)]
    conflicts = [item for item in outcomes if isinstance(item, RepositoryError)]
    assert len(successes) == len(conflicts) == 1
    assert successes[0].changed is True
    assert conflicts[0].code == "knowledge_map_revision_conflict"
    assert persisted.artifact_revision == initial.artifact_revision + 1
    if persisted.capacity_limits.artifact_byte_budget == 200_000:
        assert not persisted.evidence_snapshots
    else:
        assert persisted.capacity_limits.artifact_byte_budget == 100_000
        assert [item.scope_id for item in persisted.evidence_snapshots] == [scope_id]


def test_enrichment_and_build_share_one_cas_without_losing_the_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    IndexService().build(repository)
    built = KnowledgeMapBuildService().build(repository, budgets=_budgets()).artifact
    scope = built.scope_contracts[0]
    evidence = KnowledgeMapEvidenceService().collect(
        repository, scope_id=scope.scope_id, token_budget=10_000
    )
    payload = json.dumps(
        {
            "schema_version": "1.0",
            "scope_id": scope.scope_id,
            "expected_artifact_revision": evidence.artifact.artifact_revision,
            "records": [
                {
                    "id": f"{scope.allowed_record_kinds[0]}:contested",
                    "kind": scope.allowed_record_kinds[0],
                    "claims": [
                        {
                            "kind": "summary",
                            "text": "A complete contested enrichment.",
                            "fact_node_ids": [scope.allowed_fact_node_ids[0]],
                            "related_node_ids": [],
                            "evidence_ids": [
                                evidence.snapshot.references[0].evidence_id
                            ],
                        }
                    ],
                }
            ],
        }
    ).encode()
    initial = MapStore(repository).read_artifact()

    rendezvous = Barrier(2)
    original = MapStore.write_transaction

    def coordinated_write_transaction(
        self: MapStore, *args: object, **kwargs: object
    ) -> object:
        rendezvous.wait()
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(MapStore, "write_transaction", coordinated_write_transaction)
    service = KnowledgeMapEnrichmentService()
    with ThreadPoolExecutor(max_workers=2) as executor:
        enrich_future = executor.submit(service.enrich, repository, payload=payload)
        build_future = executor.submit(
            KnowledgeMapBuildService().build,
            repository,
            budgets=replace(_budgets(), artifact_byte_budget=200_000),
        )
        outcomes = (_outcome(enrich_future), _outcome(build_future))

    persisted = MapStore(repository).read_artifact()
    successes = [item for item in outcomes if not isinstance(item, RepositoryError)]
    conflicts = [item for item in outcomes if isinstance(item, RepositoryError)]
    assert len(successes) == len(conflicts) == 1
    assert successes[0].changed is True
    assert conflicts[0].code == "knowledge_map_revision_conflict"
    assert persisted == successes[0].artifact
    assert persisted.artifact_revision == initial.artifact_revision + 1
    assert persisted.deterministic_revision == initial.deterministic_revision
    assert persisted.evidence_snapshots == initial.evidence_snapshots
    if persisted.enrichments:
        assert persisted.capacity_limits.artifact_byte_budget == 100_000
        assert len(persisted.enrichments) == 1
        assert persisted.enrichments[0].scope_id == scope.scope_id
    else:
        assert persisted.capacity_limits.artifact_byte_budget == 200_000


def _outcome(future: Future[_ResultT]) -> _ResultT | RepositoryError:
    try:
        return future.result()
    except RepositoryError as error:
        return error


def _budgets() -> MapBuildBudgets:
    values = [100, 100_000, 100, 100, 8, 4, 20, 1, 20, 5, 20, 20, 20]
    capacities = [20, 20, 20, 10, 10, 10, 10, 10, 10_000]
    return MapBuildBudgets(*values, *capacities)  # type: ignore[arg-type]
