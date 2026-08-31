"""Deterministic Knowledge Map build lifecycle orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import load_published_index
from repo_dive.knowledge_map.analysis import analyze_importance
from repo_dive.knowledge_map.flows import (
    derive_scope_contracts,
    derive_static_flows,
    derive_tour,
)
from repo_dive.knowledge_map.lifting import lift_snapshot
from repo_dive.knowledge_map.models import (
    CapacityLimits,
    EvidenceSnapshot,
    KnowledgeMapArtifact,
    MapBuildBudgets,
    ScopeEnrichment,
)
from repo_dive.knowledge_map.snapshot import snapshot_from_published_index
from repo_dive.knowledge_map.store import MapStore
from repo_dive.knowledge_map.topology import derive_topology
from repo_dive.schema import JsonObject


@dataclass(frozen=True, slots=True)
class MapBuildResult:
    changed: bool
    artifact: KnowledgeMapArtifact
    discarded_evidence_snapshots: int
    discarded_enrichments: int


class KnowledgeMapBuildService:
    """Build complete deterministic sections and publish through the shared CAS."""

    def build(
        self,
        repository: str | Path,
        *,
        budgets: MapBuildBudgets,
    ) -> MapBuildResult:
        published = load_published_index(repository)
        snapshot = snapshot_from_published_index(
            published,
            source_fact_budget=budgets.source_fact_budget,
        )
        lifted = lift_snapshot(snapshot, budgets.derivation_parameters())
        analyzed_nodes = analyze_importance(lifted.nodes, lifted.edges)
        topology = derive_topology(
            analyzed_nodes,
            lifted.edges,
            cluster_budget=budgets.cluster_budget,
            minimum_cluster_files=budgets.minimum_cluster_files,
        )
        flow_analysis = derive_static_flows(
            analyzed_nodes,
            lifted.edges,
            flow_budget=budgets.flow_budget,
            flow_depth=budgets.flow_depth,
            nodes_per_flow=budgets.nodes_per_flow,
            edges_per_flow=budgets.edges_per_flow,
            script_entrypoints=snapshot.script_entrypoints,
        )
        flows = flow_analysis.flows
        tour_analysis = derive_tour(
            analyzed_nodes,
            topology.clusters,
            flows,
            tour_budget=budgets.tour_budget,
        )
        tour = tour_analysis.items
        scopes = derive_scope_contracts(
            analyzed_nodes,
            topology.clusters,
            flows,
            tour,
        )
        omission_reasons = list(snapshot.coverage.omission_reasons)
        if lifted.omitted_symbols:
            omission_reasons.append("node_budget")
        if lifted.omitted_edges:
            omission_reasons.append("edge_budget")
        if lifted.omitted_resolution_candidates:
            omission_reasons.append("resolution_candidate_node_budget")
        if topology.omitted_clusters:
            omission_reasons.append("cluster_budget")
        omission_reasons.extend(flow_analysis.truncation_reasons)
        if tour_analysis.omitted_count:
            omission_reasons.append("tour_budget")
        observations = set(snapshot.coverage.observations)
        if flow_analysis.no_roots:
            observations.add("flow_no_roots")
        coverage = replace(
            snapshot.coverage,
            unresolved_references=lifted.unresolved_references,
            ambiguous_references=lifted.ambiguous_references,
            included_nodes=len(analyzed_nodes),
            omitted_nodes=lifted.omitted_symbols,
            included_edges=len(lifted.edges),
            omitted_edges=lifted.omitted_edges,
            included_clusters=len(topology.clusters),
            omitted_clusters=topology.omitted_clusters,
            included_flows=flow_analysis.included_count,
            omitted_flows=flow_analysis.omitted_count,
            included_tour_items=tour_analysis.included_count,
            omitted_tour_items=tour_analysis.omitted_count,
            observations=tuple(sorted(observations)),
            omission_reasons=tuple(sorted(set(omission_reasons))),
        )
        store = MapStore(repository)
        baseline = store.read_snapshot()
        current = baseline.artifact
        initial_revision = current.artifact_revision + 1 if current is not None else 1
        deterministic = KnowledgeMapArtifact.create(
            artifact_revision=initial_revision,
            source=snapshot.source,
            derivation_parameters=budgets.derivation_parameters(),
            capacity_limits=budgets.capacity_limits(),
            coverage=coverage,
            nodes=analyzed_nodes,
            edges=lifted.edges,
            cycle_groups=topology.cycle_groups,
            clusters=topology.clusters,
            layers=topology.layers,
            flows=flows,
            tour=tour,
            scope_contracts=scopes,
        )
        deterministic_changed = (
            current is None
            or current.deterministic_revision != deterministic.deterministic_revision
        )
        evidence: tuple[EvidenceSnapshot, ...] = ()
        enrichments: tuple[ScopeEnrichment, ...] = ()
        if current is not None and not deterministic_changed:
            _validate_semantic_capacity(current, budgets.capacity_limits())
            evidence = current.evidence_snapshots
            enrichments = current.enrichments
        candidate = KnowledgeMapArtifact.create(
            artifact_revision=initial_revision,
            source=deterministic.source,
            derivation_parameters=deterministic.derivation_parameters,
            capacity_limits=deterministic.capacity_limits,
            coverage=deterministic.coverage,
            nodes=deterministic.nodes,
            edges=deterministic.edges,
            cycle_groups=deterministic.cycle_groups,
            clusters=deterministic.clusters,
            layers=deterministic.layers,
            flows=deterministic.flows,
            tour=deterministic.tour,
            scope_contracts=deterministic.scope_contracts,
            evidence_snapshots=evidence,
            enrichments=enrichments,
        )

        def revalidate() -> None:
            latest = load_published_index(repository).manifest
            if (
                latest.build_id != snapshot.source.index_build_id
                or latest.repository_fingerprint
                != snapshot.source.repository_fingerprint
            ):
                raise RepositoryError(
                    "knowledge_map_index_changed",
                    "Published index changed while building the Knowledge Map.",
                    details={
                        "recovery_action": "rerun_current_index",
                        "retry_mode": "unchanged",
                    },
                )

        def equivalent(value: KnowledgeMapArtifact) -> bool:
            return (
                value.deterministic_revision == candidate.deterministic_revision
                and value.capacity_limits == candidate.capacity_limits
            )

        with store.write_transaction(
            baseline,
            revalidate=revalidate,
        ) as transaction:
            write = transaction.commit(candidate, equivalent=equivalent)
        discarded_evidence = (
            len(current.evidence_snapshots)
            if current is not None and deterministic_changed
            else 0
        )
        discarded_enrichments = (
            len(current.enrichments)
            if current is not None and deterministic_changed
            else 0
        )
        return MapBuildResult(
            write.changed,
            write.artifact,
            discarded_evidence,
            discarded_enrichments,
        )


def _validate_semantic_capacity(
    artifact: KnowledgeMapArtifact,
    capacity: CapacityLimits,
) -> None:
    violations: list[str] = []
    if len(artifact.evidence_snapshots) > capacity.evidence_snapshots:
        violations.append("evidence_snapshots")
    if any(
        len(snapshot.references) > capacity.evidence_references_per_snapshot
        for snapshot in artifact.evidence_snapshots
    ):
        violations.append("evidence_references_per_snapshot")
    records = tuple(
        record for enrichment in artifact.enrichments for record in enrichment.records
    )
    if len(records) > capacity.enrichment_records:
        violations.append("enrichment_records")
    if any(
        len(enrichment.records) > capacity.records_per_scope
        for enrichment in artifact.enrichments
    ):
        violations.append("records_per_scope")
    if any(len(record.claims) > capacity.claims_per_record for record in records):
        violations.append("claims_per_record")
    claims = tuple(claim for record in records for claim in record.claims)
    for field_name in (
        "fact_node_ids",
        "related_node_ids",
        "evidence_ids",
    ):
        limit = getattr(capacity, f"{field_name}_per_claim")
        if any(len(getattr(claim, field_name)) > limit for claim in claims):
            violations.append(f"{field_name}_per_claim")
    if any(
        enrichment.canonical_input_bytes > capacity.enrichment_input_bytes
        for enrichment in artifact.enrichments
    ):
        violations.append("enrichment_input_bytes")
    if violations:
        raise RepositoryError(
            "knowledge_map_capacity_conflict",
            "Current semantic state exceeds the requested capacity.",
            details=JsonObject(
                {
                    "fields": list(sorted(set(violations))),
                    "recovery_action": "reset_or_restore_capacity",
                    "retry_mode": "after_recovery",
                }
            ),
        )
