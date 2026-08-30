from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import (
    IndexService,
    PublishedIndex,
    load_published_index,
)
from repo_dive.knowledge_map.build import KnowledgeMapBuildService
from repo_dive.knowledge_map.models import (
    EvidenceRef,
    EvidenceSnapshot,
    KnowledgeMapArtifact,
    MapBuildBudgets,
    RetrievalParameters,
)
from repo_dive.knowledge_map.store import MAP_ARTIFACT_PATH, MapStore


def test_build_is_byte_preserving_when_deterministic_intent_is_identical(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    IndexService().build(repository)
    service = KnowledgeMapBuildService()
    budget = _budgets()

    first = service.build(repository, budgets=budget)
    path = repository / MAP_ARTIFACT_PATH
    before = path.read_bytes()
    second = service.build(repository, budgets=budget)

    assert first.changed is True
    assert second.changed is False
    assert path.read_bytes() == before
    assert second.artifact.evidence_snapshots == ()


def test_build_reports_per_language_parser_and_relationship_coverage(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    (repository / "web.js").write_text("export function run() {}\n", encoding="utf-8")
    (repository / "README.md").write_text("# Repository\n", encoding="utf-8")
    IndexService().build(repository)

    artifact = KnowledgeMapBuildService().build(repository, budgets=_budgets()).artifact
    coverage = {item.language: item for item in artifact.coverage.parser_coverage}

    assert coverage["python"].graph_capability == "full"
    assert coverage["javascript"].graph_capability == "containment_only"
    assert coverage["markdown"].graph_capability == "none"
    assert all(item.indexed_file_count == item.file_count for item in coverage.values())
    assert all(
        item.relationship_count == sum(count for _, count in item.relationship_kinds)
        for item in coverage.values()
    )


def test_build_recovers_from_invalid_artifact_bytes(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    IndexService().build(repository)
    artifact_path = repository / MAP_ARTIFACT_PATH
    artifact_path.write_bytes(b"not-json")

    result = KnowledgeMapBuildService().build(repository, budgets=_budgets())

    assert result.changed is True
    assert result.artifact.artifact_revision == 1
    assert MapStore(repository).read_artifact() == result.artifact


def test_build_rejects_index_generation_change_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    IndexService().build(repository)
    published = load_published_index(repository)
    changed = replace(
        published,
        manifest=replace(published.manifest, build_id="changed-build"),
    )
    calls = 0

    def load_with_race(_repository: object) -> PublishedIndex:
        nonlocal calls
        calls += 1
        return published if calls == 1 else changed

    monkeypatch.setattr(
        "repo_dive.knowledge_map.build.load_published_index",
        load_with_race,
    )

    with pytest.raises(RepositoryError) as exc_info:
        KnowledgeMapBuildService().build(repository, budgets=_budgets())

    assert exc_info.value.code == "knowledge_map_index_changed"
    assert MapStore(repository).read_snapshot().state == "absent"


def test_build_preserves_current_evidence_and_discards_it_after_source_change(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    source = repository / "app.py"
    source.write_text("def main():\n    pass\n", encoding="utf-8")
    IndexService().build(repository)
    service = KnowledgeMapBuildService()
    base = service.build(repository, budgets=_budgets()).artifact
    enriched = _with_evidence(base)
    store = MapStore(repository)
    with store.write_transaction(store.read_snapshot()) as transaction:
        transaction.commit(enriched)

    unchanged = service.build(repository, budgets=_budgets())

    assert unchanged.changed is False
    assert unchanged.artifact.evidence_snapshots == enriched.evidence_snapshots

    source.write_text("def main():\n    return 1\n", encoding="utf-8")
    IndexService().build(repository)
    changed = service.build(repository, budgets=_budgets())

    assert changed.changed is True
    assert changed.discarded_evidence_snapshots == 1
    assert changed.artifact.evidence_snapshots == ()


def test_capacity_change_preserves_semantics_and_rejects_undersized_limit(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    IndexService().build(repository)
    service = KnowledgeMapBuildService()
    initial_budgets = _budgets()
    base = service.build(repository, budgets=initial_budgets).artifact
    enriched = _with_evidence(base)
    store = MapStore(repository)
    with store.write_transaction(store.read_snapshot()) as transaction:
        transaction.commit(enriched)

    expanded = service.build(
        repository,
        budgets=replace(initial_budgets, artifact_byte_budget=3_000_000),
    )

    assert expanded.changed is True
    assert expanded.artifact.evidence_snapshots == enriched.evidence_snapshots
    before = (repository / MAP_ARTIFACT_PATH).read_bytes()

    with pytest.raises(RepositoryError) as exc_info:
        service.build(
            repository,
            budgets=replace(
                initial_budgets,
                artifact_byte_budget=3_000_000,
                evidence_references_per_snapshot=1,
            ),
        )

    assert exc_info.value.code == "knowledge_map_capacity_conflict"
    assert (repository / MAP_ARTIFACT_PATH).read_bytes() == before


def _budgets() -> MapBuildBudgets:
    return MapBuildBudgets(
        1_000,
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


def _with_evidence(base: KnowledgeMapArtifact) -> KnowledgeMapArtifact:
    contract = base.scope_contracts[0]
    anchor = contract.required_anchor_fact_node_ids[0]
    snapshot = EvidenceSnapshot.create(
        schema_version="1.0",
        scope_id=contract.scope_id,
        scope_kind=contract.scope_kind,
        scope_contract_hash=contract.contract_hash,
        deterministic_revision=base.deterministic_revision,
        repository_fingerprint=base.source.repository_fingerprint,
        index_build_id=base.source.index_build_id,
        index_schema_version=base.source.index_schema_version,
        source_control=base.source.source_control,
        source_commit=base.source.source_commit,
        source_dirty=base.source.source_dirty,
        query="scope",
        query_plan_hash="plan",
        retrieval_parameters=RetrievalParameters(
            5, "hybrid", 60, (("lexical", 1.0),), 0.8
        ),
        token_budget=100,
        estimated_tokens=10,
        reserved_tokens=0,
        token_estimator="fixture",
        truncated=False,
        reference_count=2,
        references=(
            EvidenceRef(
                "evidence-1",
                "chunk-1",
                "content-1",
                "app.py",
                1,
                1,
                None,
                "direct",
                (anchor,),
            ),
            EvidenceRef(
                "evidence-2",
                "chunk-2",
                "content-2",
                "app.py",
                1,
                1,
                None,
                "direct",
                (anchor,),
            ),
        ),
    )
    return KnowledgeMapArtifact.create(
        artifact_revision=base.artifact_revision + 1,
        source=base.source,
        derivation_parameters=base.derivation_parameters,
        capacity_limits=base.capacity_limits,
        coverage=base.coverage,
        nodes=base.nodes,
        edges=base.edges,
        cycle_groups=base.cycle_groups,
        clusters=base.clusters,
        layers=base.layers,
        flows=base.flows,
        tour=base.tour,
        scope_contracts=base.scope_contracts,
        evidence_snapshots=(snapshot,),
    )
