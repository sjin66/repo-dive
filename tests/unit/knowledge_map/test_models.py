from __future__ import annotations

from dataclasses import replace

import pytest

from repo_dive.knowledge_map.models import (
    CapacityLimits,
    Cluster,
    DerivationParameters,
    EnrichmentRecord,
    EvidenceRef,
    EvidenceSnapshot,
    FactNode,
    KnowledgeMapArtifact,
    LanguageCoverage,
    MapBuildBudgets,
    MapSource,
    RetrievalParameters,
    ScopeContract,
    ScopeEnrichment,
    SemanticClaim,
    canonical_bytes,
)


def budgets() -> MapBuildBudgets:
    return MapBuildBudgets(
        source_fact_budget=100,
        artifact_byte_budget=100_000,
        node_budget=100,
        edge_budget=100,
        contributing_relationship_ids_per_edge=8,
        resolution_candidates_per_reference=4,
        cluster_budget=20,
        minimum_cluster_files=1,
        flow_budget=20,
        flow_depth=5,
        nodes_per_flow=20,
        edges_per_flow=20,
        tour_budget=20,
        evidence_snapshots=20,
        evidence_references_per_snapshot=20,
        enrichment_records=20,
        records_per_scope=10,
        claims_per_record=10,
        fact_node_ids_per_claim=10,
        related_node_ids_per_claim=10,
        evidence_ids_per_claim=10,
        enrichment_input_bytes=10_000,
    )


def test_empty_artifact_round_trips_canonically() -> None:
    artifact = KnowledgeMapArtifact.create_empty(
        source=MapSource("fingerprint", "build", 5, "git", None, True),
        budgets=budgets(),
    )

    decoded = KnowledgeMapArtifact.from_document(artifact.to_document())

    assert decoded == artifact
    assert canonical_bytes(decoded.to_document()) == canonical_bytes(
        artifact.to_document()
    )
    assert decoded.evidence_snapshots == ()
    assert decoded.enrichments == ()


def test_decoder_rejects_unknown_fields_and_hash_drift() -> None:
    artifact = KnowledgeMapArtifact.create_empty(
        source=MapSource("fingerprint", "build", 5, "non_git", None, None),
        budgets=budgets(),
    )
    unknown = artifact.to_document()
    unknown["surprise"] = True
    with pytest.raises(ValueError, match="fields"):
        KnowledgeMapArtifact.from_document(unknown)

    with pytest.raises(ValueError, match="content hash"):
        replace(artifact, content_hash="sha256:" + "0" * 64)


def test_decoder_rejects_mutable_or_wrong_typed_nested_values() -> None:
    artifact = KnowledgeMapArtifact.create_empty(
        source=MapSource("fingerprint", "build", 5, "non_git", None, None),
        budgets=budgets(),
    )
    document = artifact.to_document()
    document["artifact_revision"] = True

    with pytest.raises(ValueError, match="artifact revision"):
        KnowledgeMapArtifact.from_document(document)

    parameters = RetrievalParameters(
        max_results=5,
        strategy="hybrid",
        rrf_k=60,
        channel_weights=(("lexical", 1.0),),
        overlap_threshold=0.8,
    )
    assert isinstance(parameters.channel_weights, tuple)
    assert all(isinstance(item, tuple) for item in parameters.channel_weights)


def test_budget_fields_are_positive_and_split_by_identity_effect() -> None:
    value = budgets()
    assert isinstance(value.derivation_parameters(), DerivationParameters)
    assert isinstance(value.capacity_limits(), CapacityLimits)
    with pytest.raises(ValueError, match="positive"):
        replace(value, flow_depth=0)


def test_frozen_semantic_projections_validate_claim_owned_references() -> None:
    repository = FactNode(
        "repo", "repository", "derived", "repo", None, None, None, None, None, None
    )
    module = FactNode(
        "module",
        "module",
        "derived",
        "app",
        None,
        None,
        None,
        "python",
        "repo",
        None,
    )
    file = FactNode(
        "file",
        "file",
        "derived",
        "app.py",
        "app.py",
        None,
        None,
        "python",
        "module",
        None,
    )
    cluster = Cluster("cluster", ("file",), ("fixture_v1",), 0, 0, 0, 0)
    contract = ScopeContract.create(
        scope_id="cluster",
        scope_kind="cluster",
        allowed_fact_node_ids=("file", "module", "repo"),
        required_anchor_fact_node_ids=("file",),
        allowed_record_kinds=("cluster_label", "concept"),
        allowed_claim_kinds=(
            "label",
            "summary",
            "responsibility",
            "association",
            "concept_description",
        ),
    )
    base = KnowledgeMapArtifact.create(
        artifact_revision=1,
        source=MapSource("fingerprint", "build", 5, "non_git", None, None),
        derivation_parameters=budgets().derivation_parameters(),
        capacity_limits=budgets().capacity_limits(),
        coverage=replace(
            KnowledgeMapArtifact.create_empty(
                source=MapSource("fingerprint", "build", 5, "non_git", None, None),
                budgets=budgets(),
            ).coverage,
            total_files=1,
            indexed_files=1,
            included_nodes=3,
            included_clusters=1,
            languages=(("python", 1),),
            parser_coverage=(LanguageCoverage("python", 1, 1, 0, 0, (), "full"),),
        ),
        nodes=(repository, module, file),
        clusters=(cluster,),
        scope_contracts=(contract,),
    )
    reference = EvidenceRef(
        "evidence", "chunk", "hash", "app.py", 1, 1, None, "definition", ("file",)
    )
    retrieval = RetrievalParameters(
        max_results=5,
        strategy="hybrid",
        rrf_k=60,
        channel_weights=(("lexical", 1.0),),
        overlap_threshold=0.8,
    )
    snapshot = EvidenceSnapshot.create(
        schema_version="1.0",
        scope_id="cluster",
        scope_kind="cluster",
        scope_contract_hash=contract.contract_hash,
        deterministic_revision=base.deterministic_revision,
        repository_fingerprint="fingerprint",
        index_build_id="build",
        index_schema_version=5,
        source_control="non_git",
        source_commit=None,
        source_dirty=None,
        query="cluster",
        query_plan_hash="sha256:plan",
        retrieval_parameters=retrieval,
        token_budget=100,
        estimated_tokens=10,
        reserved_tokens=0,
        token_estimator="fixture_v1",
        truncated=False,
        reference_count=1,
        references=(reference,),
    )
    record = EnrichmentRecord(
        "label",
        "cluster_label",
        (SemanticClaim("label", "Application", ("file",), (), ("evidence",)),),
    )
    enrichment = ScopeEnrichment.create(
        schema_version="1.0",
        scope_id="cluster",
        scope_kind="cluster",
        scope_contract_hash=contract.contract_hash,
        evidence_snapshot_hash=snapshot.snapshot_hash,
        records=(record,),
    )

    artifact = KnowledgeMapArtifact.create(
        artifact_revision=2,
        source=base.source,
        derivation_parameters=base.derivation_parameters,
        capacity_limits=base.capacity_limits,
        coverage=base.coverage,
        nodes=base.nodes,
        clusters=base.clusters,
        scope_contracts=base.scope_contracts,
        evidence_snapshots=(snapshot,),
        enrichments=(enrichment,),
    )

    assert KnowledgeMapArtifact.from_document(artifact.to_document()) == artifact
