"""Claim validation, complete-scope replacement, reset, and semantic health."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import load_published_index
from repo_dive.knowledge_map.evidence_service import validate_evidence_freshness
from repo_dive.knowledge_map.models import (
    EvidenceSnapshot,
    KnowledgeMapArtifact,
    ScopeContract,
    ScopeEnrichment,
)
from repo_dive.knowledge_map.store import MapStore
from repo_dive.knowledge_map.submission import (
    EnrichmentSubmission,
    decode_enrichment_submission,
)


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    changed: bool
    artifact: KnowledgeMapArtifact
    scope_id: str


@dataclass(frozen=True, slots=True)
class SemanticValidationResult:
    valid: bool
    artifact_revision: int
    checked_scopes: int
    checked_claims: int
    validation_scope: tuple[str, ...] = (
        "schema",
        "reference_integrity",
        "scope_ownership",
        "evidence_freshness",
    )
    semantic_entailment_checked: bool = False


class KnowledgeMapEnrichmentService:
    """Apply semantic changes without changing any deterministic map section."""

    def enrich(self, repository: str | Path, *, payload: bytes) -> EnrichmentResult:
        submission = decode_enrichment_submission(payload)
        published = load_published_index(repository)
        store = MapStore(repository)
        baseline = store.read_snapshot()
        artifact = store.read_artifact()
        _validate_source(
            artifact,
            published.manifest.build_id,
            published.manifest.repository_fingerprint,
        )
        enrichment = _validate_submission(repository, artifact, submission)
        current = next(
            (
                item
                for item in artifact.enrichments
                if item.scope_id == submission.scope_id
            ),
            None,
        )
        if (
            current is None
            or current.scope_content_hash != enrichment.scope_content_hash
        ) and submission.expected_artifact_revision != artifact.artifact_revision:
            _revision_conflict()
        candidate = _with_enrichment(artifact, enrichment)

        def revalidate() -> None:
            latest = load_published_index(repository)
            _ensure_index_unchanged(
                artifact,
                latest.manifest.build_id,
                latest.manifest.repository_fingerprint,
            )

        def equivalent(value: KnowledgeMapArtifact) -> bool:
            desired = _validate_submission(repository, value, submission)
            existing = next(
                (
                    item
                    for item in value.enrichments
                    if item.scope_id == submission.scope_id
                ),
                None,
            )
            if (
                existing is not None
                and existing.scope_content_hash == desired.scope_content_hash
            ):
                return True
            if submission.expected_artifact_revision != value.artifact_revision:
                _revision_conflict()
            return False

        with store.write_transaction(baseline, revalidate=revalidate) as transaction:
            write = transaction.commit(candidate, equivalent=equivalent)
        return EnrichmentResult(write.changed, write.artifact, submission.scope_id)

    def reset(self, repository: str | Path, *, scope_id: str) -> EnrichmentResult:
        published = load_published_index(repository)
        store = MapStore(repository)
        baseline = store.read_snapshot()
        artifact = store.read_artifact()
        _validate_source(
            artifact,
            published.manifest.build_id,
            published.manifest.repository_fingerprint,
        )
        _scope(artifact, scope_id)
        candidate = _without_scope_semantics(artifact, scope_id)

        def revalidate() -> None:
            latest = load_published_index(repository)
            _ensure_index_unchanged(
                artifact,
                latest.manifest.build_id,
                latest.manifest.repository_fingerprint,
            )

        def equivalent(value: KnowledgeMapArtifact) -> bool:
            _scope(value, scope_id)
            return not any(
                item.scope_id == scope_id for item in value.evidence_snapshots
            ) and not any(item.scope_id == scope_id for item in value.enrichments)

        with store.write_transaction(baseline, revalidate=revalidate) as transaction:
            write = transaction.commit(candidate, equivalent=equivalent)
        return EnrichmentResult(write.changed, write.artifact, scope_id)

    def validate(self, repository: str | Path) -> SemanticValidationResult:
        """Report structural ownership/freshness only, never semantic truth."""
        published = load_published_index(repository)
        artifact = MapStore(repository).read_artifact()
        _validate_source(
            artifact,
            published.manifest.build_id,
            published.manifest.repository_fingerprint,
        )
        for snapshot in artifact.evidence_snapshots:
            validate_evidence_freshness(repository, artifact, snapshot)
        return SemanticValidationResult(
            valid=True,
            artifact_revision=artifact.artifact_revision,
            checked_scopes=len(artifact.evidence_snapshots),
            checked_claims=sum(
                len(record.claims)
                for enrichment in artifact.enrichments
                for record in enrichment.records
            ),
        )


def _validate_submission(
    repository: str | Path,
    artifact: KnowledgeMapArtifact,
    submission: EnrichmentSubmission,
) -> ScopeEnrichment:
    contract = _scope(artifact, submission.scope_id)
    snapshot = next(
        (
            item
            for item in artifact.evidence_snapshots
            if item.scope_id == submission.scope_id
        ),
        None,
    )
    if snapshot is None:
        raise RepositoryError(
            "knowledge_map_evidence_not_found",
            "Knowledge Map scope has no current Evidence snapshot.",
            details={
                "recovery_action": "collect_evidence",
                "retry_mode": "after_recovery",
            },
        )
    validate_evidence_freshness(repository, artifact, snapshot)
    limits = artifact.capacity_limits
    if submission.raw_input_bytes > limits.enrichment_input_bytes:
        _budget_error("raw_input_bytes")
    if len(submission.records) > limits.records_per_scope:
        _budget_error("records_per_scope")
    other_record_count = sum(
        len(item.records)
        for item in artifact.enrichments
        if item.scope_id != submission.scope_id
    )
    if other_record_count + len(submission.records) > limits.enrichment_records:
        _budget_error("enrichment_records")
    evidence_ids = {item.evidence_id for item in snapshot.references}
    permissions = {
        "cluster_label": {"label", "summary", "responsibility", "association"},
        "flow_explanation": {"label", "summary", "flow_explanation", "association"},
        "concept": {"label", "summary", "concept_description", "association"},
        "reading_guidance": {"label", "summary", "reading_guidance", "association"},
    }
    for record in submission.records:
        if record.kind not in contract.allowed_record_kinds:
            _reference_error(submission.scope_id)
        if len(record.claims) > limits.claims_per_record:
            _budget_error("claims_per_record")
        for claim in record.claims:
            if (
                claim.kind not in contract.allowed_claim_kinds
                or claim.kind not in permissions[record.kind]
            ):
                _reference_error(submission.scope_id)
            if (
                not set(claim.fact_node_ids) <= set(contract.allowed_fact_node_ids)
                or not set(claim.related_node_ids)
                <= set(contract.allowed_fact_node_ids)
                or not set(claim.evidence_ids) <= evidence_ids
            ):
                _reference_error(submission.scope_id)
            for field in ("fact_node_ids", "related_node_ids", "evidence_ids"):
                if len(getattr(claim, field)) > getattr(limits, f"{field}_per_claim"):
                    _budget_error(f"{field}_per_claim")
    enrichment = ScopeEnrichment.create(
        schema_version=submission.schema_version,
        scope_id=submission.scope_id,
        scope_kind=contract.scope_kind,
        scope_contract_hash=contract.contract_hash,
        evidence_snapshot_hash=snapshot.snapshot_hash,
        records=submission.records,
    )
    if enrichment.canonical_input_bytes > limits.enrichment_input_bytes:
        _budget_error("enrichment_input_bytes")
    return enrichment


def _scope(artifact: KnowledgeMapArtifact, scope_id: str) -> ScopeContract:
    contract = next(
        (item for item in artifact.scope_contracts if item.scope_id == scope_id), None
    )
    if contract is None:
        raise RepositoryError(
            "knowledge_map_scope_not_found",
            "Knowledge Map scope does not exist.",
            details={
                "recovery_action": "select_current_scope",
                "retry_mode": "after_recovery",
                "scope_id": scope_id,
            },
        )
    return contract


def _artifact_copy(
    artifact: KnowledgeMapArtifact,
    *,
    evidence_snapshots: tuple[EvidenceSnapshot, ...] | None = None,
    enrichments: tuple[ScopeEnrichment, ...] | None = None,
) -> KnowledgeMapArtifact:
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
        evidence_snapshots=(
            artifact.evidence_snapshots
            if evidence_snapshots is None
            else evidence_snapshots
        ),
        enrichments=artifact.enrichments if enrichments is None else enrichments,
    )


def _with_enrichment(
    artifact: KnowledgeMapArtifact, enrichment: ScopeEnrichment
) -> KnowledgeMapArtifact:
    values = tuple(
        sorted(
            (
                *(
                    item
                    for item in artifact.enrichments
                    if item.scope_id != enrichment.scope_id
                ),
                enrichment,
            ),
            key=lambda item: item.scope_id,
        )
    )
    return _artifact_copy(artifact, enrichments=values)


def _without_scope_semantics(
    artifact: KnowledgeMapArtifact, scope_id: str
) -> KnowledgeMapArtifact:
    return _artifact_copy(
        artifact,
        evidence_snapshots=tuple(
            item for item in artifact.evidence_snapshots if item.scope_id != scope_id
        ),
        enrichments=tuple(
            item for item in artifact.enrichments if item.scope_id != scope_id
        ),
    )


def _validate_source(
    artifact: KnowledgeMapArtifact, build_id: str, fingerprint: str
) -> None:
    if (
        artifact.source.index_build_id != build_id
        or artifact.source.repository_fingerprint != fingerprint
    ):
        raise RepositoryError(
            "knowledge_map_stale",
            "Knowledge Map does not match the current published index.",
            details={"recovery_action": "rebuild_map", "retry_mode": "after_recovery"},
        )


def _reference_error(scope_id: str) -> None:
    raise RepositoryError(
        "knowledge_map_enrichment_reference_invalid",
        "Knowledge Map enrichment contains an unknown or wrong-scope reference.",
        details={
            "recovery_action": "regenerate_current_scope_submission",
            "retry_mode": "after_recovery",
            "scope_id": scope_id,
        },
    )


def _budget_error(field: str) -> None:
    raise RepositoryError(
        "knowledge_map_enrichment_budget_exceeded",
        "Knowledge Map enrichment exceeds persisted capacity.",
        details={
            "field": field,
            "recovery_action": "reduce_enrichment_or_raise_capacity",
            "retry_mode": "after_recovery",
        },
    )


def _revision_conflict() -> None:
    raise RepositoryError(
        "knowledge_map_revision_conflict",
        "Knowledge Map changed after enrichment generation.",
        details={"recovery_action": "reload_artifact", "retry_mode": "after_reload"},
    )


def _ensure_index_unchanged(
    artifact: KnowledgeMapArtifact, build_id: str, fingerprint: str
) -> None:
    if (
        artifact.source.index_build_id != build_id
        or artifact.source.repository_fingerprint != fingerprint
    ):
        raise RepositoryError(
            "knowledge_map_index_changed",
            "Published index changed during the Knowledge Map operation.",
            details={
                "recovery_action": "rerun_current_index",
                "retry_mode": "unchanged",
            },
        )


__all__ = [
    "EnrichmentResult",
    "KnowledgeMapEnrichmentService",
    "SemanticValidationResult",
]
