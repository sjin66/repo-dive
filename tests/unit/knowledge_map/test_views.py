from __future__ import annotations

from pathlib import Path
from typing import cast

from repo_dive.indexing.service import IndexService
from repo_dive.knowledge_map.build import KnowledgeMapBuildService
from repo_dive.knowledge_map.models import (
    EnrichmentRecord,
    EvidenceRef,
    EvidenceSnapshot,
    KnowledgeMapArtifact,
    RetrievalParameters,
    ScopeEnrichment,
    SemanticClaim,
)
from repo_dive.knowledge_map.views import (
    project_architecture,
    project_flows,
    project_tour,
)

from .test_build import _budgets


def test_views_are_bounded_and_do_not_mutate_artifact(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    IndexService().build(repository)
    artifact = KnowledgeMapBuildService().build(repository, budgets=_budgets()).artifact
    before = artifact.content_hash

    architecture = project_architecture(artifact, max_results=1)
    flows = project_flows(artifact, max_results=1)
    tour = project_tour(artifact, max_results=1)

    assert cast(int, architecture["included_count"]) <= 1
    assert cast(int, flows["included_count"]) <= 1
    assert cast(int, tour["included_count"]) <= 1
    assert artifact.content_hash == before


def test_architecture_merges_optional_scope_label_without_changing_facts(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    IndexService().build(repository)
    base = KnowledgeMapBuildService().build(repository, budgets=_budgets()).artifact
    contract = next(
        item for item in base.scope_contracts if item.scope_kind == "cluster"
    )
    reference = EvidenceRef(
        "evidence",
        "chunk",
        "hash",
        "app.py",
        1,
        1,
        None,
        "direct",
        (contract.required_anchor_fact_node_ids[0],),
    )
    snapshot = EvidenceSnapshot.create(
        schema_version="1.0",
        scope_id=contract.scope_id,
        scope_kind="cluster",
        scope_contract_hash=contract.contract_hash,
        deterministic_revision=base.deterministic_revision,
        repository_fingerprint=base.source.repository_fingerprint,
        index_build_id=base.source.index_build_id,
        index_schema_version=base.source.index_schema_version,
        source_control=base.source.source_control,
        source_commit=base.source.source_commit,
        source_dirty=base.source.source_dirty,
        query="cluster",
        query_plan_hash="plan",
        retrieval_parameters=RetrievalParameters(
            5, "hybrid", 60, (("lexical", 1.0),), 0.8
        ),
        token_budget=100,
        estimated_tokens=10,
        reserved_tokens=0,
        token_estimator="fixture",
        truncated=False,
        reference_count=1,
        references=(reference,),
    )
    record = EnrichmentRecord(
        "label",
        "cluster_label",
        (
            SemanticClaim(
                "label",
                "Application Core",
                (contract.required_anchor_fact_node_ids[0],),
                (),
                ("evidence",),
            ),
        ),
    )
    enrichment = ScopeEnrichment.create(
        schema_version="1.0",
        scope_id=contract.scope_id,
        scope_kind="cluster",
        scope_contract_hash=contract.contract_hash,
        evidence_snapshot_hash=snapshot.snapshot_hash,
        records=(record,),
    )
    enriched = KnowledgeMapArtifact.create(
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
        enrichments=(enrichment,),
    )

    projection = project_architecture(enriched, max_results=100)
    items = cast(list[dict[str, object]], projection["items"])
    cluster_item = next(item for item in items if item.get("id") == contract.scope_id)

    assert cluster_item["presentation_label"] == "Application Core"
    assert enriched.nodes == base.nodes
