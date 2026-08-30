from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import IndexService
from repo_dive.knowledge_map.build import KnowledgeMapBuildService
from repo_dive.knowledge_map.enrichment_service import KnowledgeMapEnrichmentService
from repo_dive.knowledge_map.evidence_service import KnowledgeMapEvidenceService
from repo_dive.knowledge_map.models import (
    EvidenceSnapshot,
    KnowledgeMapArtifact,
    MapBuildBudgets,
)
from repo_dive.knowledge_map.store import MAP_ARTIFACT_PATH, MapStore


def test_scope_evidence_enrichment_replay_validation_and_reset(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    built = KnowledgeMapBuildService().build(repository, budgets=_budgets()).artifact
    scope = built.scope_contracts[0]
    evidence_service = KnowledgeMapEvidenceService()

    first = evidence_service.collect(
        repository, scope_id=scope.scope_id, token_budget=10_000
    )
    before_replay = (repository / MAP_ARTIFACT_PATH).read_bytes()
    replay = evidence_service.collect(
        repository, scope_id=scope.scope_id, token_budget=10_000
    )

    assert first.changed is True
    assert replay.changed is False
    assert (repository / MAP_ARTIFACT_PATH).read_bytes() == before_replay
    assert first.snapshot.references
    assert [source.reference for source in first.sources] == list(
        first.snapshot.references
    )
    assert all(source.text for source in first.sources)

    replacement = evidence_service.collect(
        repository, scope_id=scope.scope_id, token_budget=9_000
    )
    assert replacement.changed is True
    assert replacement.snapshot.snapshot_hash != first.snapshot.snapshot_hash

    claim_kind = {
        "cluster": "summary",
        "flow": "flow_explanation",
        "tour": "reading_guidance",
    }[scope.scope_kind]
    record_kind = scope.allowed_record_kinds[0]
    payload = json.dumps(
        {
            "schema_version": "1.0",
            "scope_id": scope.scope_id,
            "expected_artifact_revision": replacement.artifact.artifact_revision,
            "records": [
                {
                    "id": f"{record_kind}:fixture",
                    "kind": record_kind,
                    "claims": [
                        {
                            "kind": claim_kind,
                            "text": (
                                "This statement is reference-validated, "
                                "not truth-scored."
                            ),
                            "fact_node_ids": [scope.allowed_fact_node_ids[0]],
                            "related_node_ids": [],
                            "evidence_ids": [
                                replacement.snapshot.references[0].evidence_id
                            ],
                        }
                    ],
                }
            ],
        }
    ).encode("utf-8")
    enrichment_service = KnowledgeMapEnrichmentService()
    enriched = enrichment_service.enrich(repository, payload=payload)
    enriched_bytes = (repository / MAP_ARTIFACT_PATH).read_bytes()
    idempotent = enrichment_service.enrich(repository, payload=payload)
    health = enrichment_service.validate(repository)

    assert enriched.changed is True
    assert idempotent.changed is False
    assert (repository / MAP_ARTIFACT_PATH).read_bytes() == enriched_bytes
    assert health.valid is True
    assert health.semantic_entailment_checked is False
    assert health.checked_claims == 1

    other_scope = next(
        item for item in built.scope_contracts if item.scope_id != scope.scope_id
    )
    unrelated = evidence_service.collect(
        repository, scope_id=other_scope.scope_id, token_budget=10_000
    )
    after_unrelated = (repository / MAP_ARTIFACT_PATH).read_bytes()
    stale_revision_replay = enrichment_service.enrich(repository, payload=payload)
    other_snapshot = next(
        item
        for item in unrelated.artifact.evidence_snapshots
        if item.scope_id == other_scope.scope_id
    )

    assert unrelated.changed is True
    assert stale_revision_replay.changed is False
    assert (repository / MAP_ARTIFACT_PATH).read_bytes() == after_unrelated

    with pytest.raises(RepositoryError) as conflict:
        evidence_service.collect(
            repository, scope_id=scope.scope_id, token_budget=10_000
        )
    assert conflict.value.code == "knowledge_map_evidence_conflict"

    reset = enrichment_service.reset(repository, scope_id=scope.scope_id)
    pending = enrichment_service.reset(repository, scope_id=scope.scope_id)

    assert reset.changed is True
    assert pending.changed is False
    assert reset.artifact.deterministic_revision == built.deterministic_revision
    assert not any(
        item.scope_id == scope.scope_id for item in reset.artifact.evidence_snapshots
    )
    assert not any(
        item.scope_id == scope.scope_id for item in reset.artifact.enrichments
    )
    assert (
        next(
            item
            for item in reset.artifact.evidence_snapshots
            if item.scope_id == other_scope.scope_id
        )
        == other_snapshot
    )


def test_required_evidence_budget_failure_preserves_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository(tmp_path)
    artifact = KnowledgeMapBuildService().build(repository, budgets=_budgets()).artifact
    before = (repository / MAP_ARTIFACT_PATH).read_bytes()
    monkeypatch.setattr(
        "repo_dive.knowledge_map.evidence_service.search_repository",
        lambda *args, **kwargs: pytest.fail(
            "supplemental retrieval ran before the mandatory Evidence budget check"
        ),
    )

    with pytest.raises(RepositoryError) as exc_info:
        KnowledgeMapEvidenceService().collect(
            repository,
            scope_id=artifact.scope_contracts[0].scope_id,
            token_budget=1,
        )

    assert exc_info.value.code == "knowledge_map_evidence_budget_insufficient"
    assert exc_info.value.details is not None
    assert "required_tokens" in exc_info.value.details
    assert (repository / MAP_ARTIFACT_PATH).read_bytes() == before


def test_stale_scope_evidence_blocks_recollection_and_preserves_artifact(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    artifact = KnowledgeMapBuildService().build(repository, budgets=_budgets()).artifact
    scope_id = artifact.scope_contracts[0].scope_id
    collected = KnowledgeMapEvidenceService().collect(
        repository, scope_id=scope_id, token_budget=10_000
    )
    stale = _replace_snapshot_content_hash(
        collected.artifact,
        collected.snapshot,
        "sha256:stale",
    )
    store = MapStore(repository)
    with store.write_transaction(store.read_snapshot()) as transaction:
        transaction.commit(stale)
    before = (repository / MAP_ARTIFACT_PATH).read_bytes()

    with pytest.raises(RepositoryError) as exc_info:
        KnowledgeMapEvidenceService().collect(
            repository, scope_id=scope_id, token_budget=9_000
        )

    assert exc_info.value.code == "knowledge_map_evidence_stale"
    assert (repository / MAP_ARTIFACT_PATH).read_bytes() == before

    reset = KnowledgeMapEnrichmentService().reset(repository, scope_id=scope_id)
    assert reset.changed is True


def test_wrong_scope_claim_reference_preserves_evidence_snapshot(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    artifact = KnowledgeMapBuildService().build(repository, budgets=_budgets()).artifact
    scope = artifact.scope_contracts[0]
    result = KnowledgeMapEvidenceService().collect(
        repository, scope_id=scope.scope_id, token_budget=10_000
    )
    outside = "symbol:not-in-scope"
    before = (repository / MAP_ARTIFACT_PATH).read_bytes()
    payload = json.dumps(
        {
            "schema_version": "1.0",
            "scope_id": scope.scope_id,
            "expected_artifact_revision": result.artifact.artifact_revision,
            "records": [
                {
                    "id": "concept:wrong-scope",
                    "kind": "concept",
                    "claims": [
                        {
                            "kind": "concept_description",
                            "text": "Wrong scope.",
                            "fact_node_ids": [outside],
                            "related_node_ids": [],
                            "evidence_ids": [result.snapshot.references[0].evidence_id],
                        }
                    ],
                }
            ],
        }
    ).encode()

    with pytest.raises(RepositoryError) as exc_info:
        KnowledgeMapEnrichmentService().enrich(repository, payload=payload)

    assert exc_info.value.code == "knowledge_map_enrichment_reference_invalid"
    assert (repository / MAP_ARTIFACT_PATH).read_bytes() == before


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text(
        "def helper():\n    return 1\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    IndexService().build(repository)
    return repository


def _budgets() -> MapBuildBudgets:
    return MapBuildBudgets(
        10_000,
        2_000_000,
        1_000,
        3_000,
        32,
        8,
        100,
        1,
        100,
        5,
        30,
        29,
        100,
        200,
        128,
        1_000,
        32,
        32,
        32,
        32,
        16,
        1_000_000,
    )


def _replace_snapshot_content_hash(
    artifact: KnowledgeMapArtifact,
    snapshot: EvidenceSnapshot,
    content_hash: str,
) -> KnowledgeMapArtifact:
    reference = replace(snapshot.references[0], content_hash=content_hash)
    snapshot_values = {
        item.name: getattr(snapshot, item.name)
        for item in fields(snapshot)
        if item.name not in {"references", "snapshot_hash"}
    }
    stale_snapshot = EvidenceSnapshot.create(
        **snapshot_values,
        references=(reference, *snapshot.references[1:]),
    )
    return KnowledgeMapArtifact.create(
        artifact_revision=artifact.artifact_revision + 1,
        source=artifact.source,
        derivation_parameters=artifact.derivation_parameters,
        capacity_limits=artifact.capacity_limits,
        coverage=artifact.coverage,
        nodes=artifact.nodes,
        edges=artifact.edges,
        cycle_groups=artifact.cycle_groups,
        clusters=artifact.clusters,
        layers=artifact.layers,
        flows=artifact.flows,
        tour=artifact.tour,
        scope_contracts=artifact.scope_contracts,
        evidence_snapshots=(stale_snapshot,),
        enrichments=artifact.enrichments,
    )
