"""Collect and persist bounded scope Evidence through the shared map writer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repo_dive.context.packer import (
    EvidenceBundle,
    EvidencePacker,
    RequiredEvidenceBudgetError,
)
from repo_dive.errors import RepositoryError
from repo_dive.indexing.manifest import ManifestFile
from repo_dive.indexing.service import load_published_index
from repo_dive.indexing.store import IndexStore
from repo_dive.knowledge_map.evidence import ScopeEvidencePlan, plan_scope_evidence
from repo_dive.knowledge_map.models import (
    KNOWLEDGE_MAP_SCHEMA_VERSION,
    EvidenceRef,
    EvidenceSnapshot,
    KnowledgeMapArtifact,
    RetrievalParameters,
)
from repo_dive.knowledge_map.store import MapStore
from repo_dive.parsing.models import Chunk, Symbol
from repo_dive.retrieval.fusion import (
    DEFAULT_OVERLAP_THRESHOLD,
    DEFAULT_RRF_K,
    SearchHit,
)
from repo_dive.retrieval.service import MAX_RESULTS, search_repository


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """Complete source Chunk returned to the caller, never persisted in audit data."""

    reference: EvidenceRef
    text: str


@dataclass(frozen=True, slots=True)
class ScopeEvidenceResult:
    changed: bool
    artifact: KnowledgeMapArtifact
    snapshot: EvidenceSnapshot
    sources: tuple[EvidenceSource, ...]
    omitted_references: int


class KnowledgeMapEvidenceService:
    """Plan, retrieve, validate, and persist one current snapshot per scope."""

    def collect(
        self,
        repository: str | Path,
        *,
        scope_id: str,
        token_budget: int,
    ) -> ScopeEvidenceResult:
        if type(token_budget) is not int or token_budget <= 0:
            raise ValueError("token budget must be positive")
        published = load_published_index(repository)
        store = MapStore(repository)
        baseline = store.read_snapshot()
        artifact = store.read_artifact()
        _validate_map_source(
            artifact,
            published.manifest.build_id,
            published.manifest.repository_fingerprint,
        )
        chunks, symbols = _load_facts(published.database, published.manifest.files)
        capacity = artifact.capacity_limits.evidence_references_per_snapshot
        parameters = RetrievalParameters(
            max_results=min(MAX_RESULTS, capacity),
            strategy="weighted_rrf",
            rrf_k=DEFAULT_RRF_K,
            channel_weights=(("lexical", 1.0), ("structural", 1.0)),
            overlap_threshold=DEFAULT_OVERLAP_THRESHOLD,
        )
        plan = plan_scope_evidence(
            artifact,
            scope_id,
            chunks=chunks,
            symbols=symbols,
            retrieval_parameters=parameters,
        )
        existing = next(
            (item for item in artifact.evidence_snapshots if item.scope_id == scope_id),
            None,
        )
        if existing is not None:
            _validate_references(published.database, existing)
        if (
            existing is None
            and len(artifact.evidence_snapshots)
            >= artifact.capacity_limits.evidence_snapshots
        ):
            _capacity_error(
                "Evidence snapshot capacity is exhausted.",
                required=len(artifact.evidence_snapshots) + 1,
                provided=artifact.capacity_limits.evidence_snapshots,
            )
        if len(plan.required_chunks) > capacity:
            _capacity_error(
                "Required Evidence references exceed persisted capacity.",
                required=len(plan.required_chunks),
                provided=capacity,
            )

        mandatory = tuple(_direct_hit(item.chunk) for item in plan.required_chunks)
        packer = EvidencePacker()
        _pack_evidence(
            packer,
            plan.query,
            (),
            token_budget=token_budget,
            mandatory=mandatory,
        )
        search = search_repository(
            repository,
            plan.query,
            max_results=parameters.max_results,
        )
        if search.build_id != artifact.source.index_build_id:
            _index_changed()
        bundle = _pack_evidence(
            packer,
            plan.query,
            search.fusion.hits,
            token_budget=token_budget,
            mandatory=mandatory,
        )
        included_items = bundle.items[:capacity]
        omitted = len(bundle.items) - len(included_items) + len(bundle.excluded)
        direct_anchors = {
            item.chunk.id: item.anchor_fact_node_ids for item in plan.required_chunks
        }
        references = tuple(
            _reference_for_hit(
                item.id,
                item.hit,
                artifact,
                plan,
                direct_anchors,
            )
            for item in included_items
        )
        selected_tokens = bundle.reserved_tokens + sum(
            item.estimated_tokens for item in included_items
        )
        snapshot = EvidenceSnapshot.create(
            schema_version=KNOWLEDGE_MAP_SCHEMA_VERSION,
            scope_id=scope_id,
            scope_kind=plan.contract.scope_kind,
            scope_contract_hash=plan.contract.contract_hash,
            deterministic_revision=artifact.deterministic_revision,
            repository_fingerprint=artifact.source.repository_fingerprint,
            index_build_id=artifact.source.index_build_id,
            index_schema_version=artifact.source.index_schema_version,
            source_control=artifact.source.source_control,
            source_commit=artifact.source.source_commit,
            source_dirty=artifact.source.source_dirty,
            query=plan.query,
            query_plan_hash=plan.query_plan_hash,
            retrieval_parameters=parameters,
            token_budget=token_budget,
            estimated_tokens=selected_tokens,
            reserved_tokens=bundle.reserved_tokens,
            token_estimator=bundle.estimator,
            truncated=bool(omitted),
            reference_count=len(references),
            references=references,
        )
        if (
            existing is not None
            and existing.snapshot_hash != snapshot.snapshot_hash
            and any(item.scope_id == scope_id for item in artifact.enrichments)
        ):
            _evidence_conflict(scope_id)
        candidate = _with_snapshot(artifact, snapshot)

        def revalidate() -> None:
            latest = load_published_index(repository)
            _ensure_index_unchanged(
                artifact,
                latest.manifest.build_id,
                latest.manifest.repository_fingerprint,
            )

        def equivalent(current: KnowledgeMapArtifact) -> bool:
            _validate_map_source(
                current,
                artifact.source.index_build_id,
                artifact.source.repository_fingerprint,
            )
            current_snapshot = next(
                (
                    item
                    for item in current.evidence_snapshots
                    if item.scope_id == scope_id
                ),
                None,
            )
            if current_snapshot is not None:
                _validate_references(published.database, current_snapshot)
            if (
                current_snapshot is not None
                and current_snapshot.snapshot_hash == snapshot.snapshot_hash
            ):
                return True
            if current_snapshot is not None and any(
                item.scope_id == scope_id for item in current.enrichments
            ):
                _evidence_conflict(scope_id)
            return False

        with store.write_transaction(baseline, revalidate=revalidate) as transaction:
            write = transaction.commit(candidate, equivalent=equivalent)
        persisted = next(
            item
            for item in write.artifact.evidence_snapshots
            if item.scope_id == scope_id
        )
        texts = {item.hit.chunk.id: item.hit.chunk.text for item in included_items}
        return ScopeEvidenceResult(
            write.changed,
            write.artifact,
            persisted,
            tuple(
                EvidenceSource(ref, texts[ref.chunk_id]) for ref in persisted.references
            ),
            omitted,
        )


def validate_evidence_freshness(
    repository: str | Path,
    artifact: KnowledgeMapArtifact,
    snapshot: EvidenceSnapshot,
) -> None:
    """Validate index identity and every persisted Chunk projection."""
    published = load_published_index(repository)
    _validate_map_source(
        artifact, published.manifest.build_id, published.manifest.repository_fingerprint
    )
    _validate_references(published.database, snapshot)


def _load_facts(
    database: Path, manifest_files: tuple[ManifestFile, ...]
) -> tuple[tuple[Chunk, ...], tuple[Symbol, ...]]:
    symbols: list[Symbol] = []
    with IndexStore.open_readonly(database) as index:
        chunks = index.get_chunks()
        for entry in manifest_files:
            symbols.extend(index.get_parse_result(entry.path).symbols)
    return chunks, tuple(symbols)


def _direct_hit(chunk: Chunk) -> SearchHit:
    return SearchHit(chunk, None, None, None, 0.0, ("required_scope_anchor",))


def _pack_evidence(
    packer: EvidencePacker,
    query: str,
    hits: tuple[SearchHit, ...],
    *,
    token_budget: int,
    mandatory: tuple[SearchHit, ...],
) -> EvidenceBundle:
    try:
        return packer.pack(
            query,
            hits,
            token_budget=token_budget,
            required_hits=mandatory,
        )
    except RequiredEvidenceBudgetError as error:
        raise RepositoryError(
            "knowledge_map_evidence_budget_insufficient",
            "Required complete Evidence exceeds the token budget.",
            details={
                "provided_tokens": token_budget,
                "required_tokens": error.required_tokens,
                "recovery_action": "raise_token_budget",
                "retry_mode": "after_recovery",
            },
        ) from error


def _reference_for_hit(
    evidence_id: str,
    hit: SearchHit,
    artifact: KnowledgeMapArtifact,
    plan: ScopeEvidencePlan,
    direct_anchors: dict[str, tuple[str, ...]],
) -> EvidenceRef:
    anchors = direct_anchors.get(hit.chunk.id)
    role = "direct" if anchors is not None else "supplemental"
    if anchors is None:
        matching_symbol = next(
            (
                node.id
                for node in artifact.nodes
                if node.parser_symbol_id == hit.chunk.symbol_id
                and node.id in plan.contract.allowed_fact_node_ids
            ),
            None,
        )
        matching_file = next(
            (
                node.id
                for node in artifact.nodes
                if node.kind == "file"
                and node.path == hit.chunk.path
                and node.id in plan.contract.allowed_fact_node_ids
            ),
            None,
        )
        # The caller validates scope membership; use the current scope's first anchor
        # when retrieval finds contextual code outside a symbol definition.
        anchors = (
            matching_symbol
            or matching_file
            or plan.contract.required_anchor_fact_node_ids[0],
        )
    return EvidenceRef(
        evidence_id,
        hit.chunk.id,
        hit.chunk.content_hash,
        hit.chunk.path,
        hit.chunk.start_line,
        hit.chunk.end_line,
        hit.chunk.symbol_id,
        role,
        anchors,
    )


def _with_snapshot(
    artifact: KnowledgeMapArtifact, snapshot: EvidenceSnapshot
) -> KnowledgeMapArtifact:
    snapshots = tuple(
        sorted(
            (
                *(
                    item
                    for item in artifact.evidence_snapshots
                    if item.scope_id != snapshot.scope_id
                ),
                snapshot,
            ),
            key=lambda item: item.scope_id,
        )
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
        evidence_snapshots=snapshots,
        enrichments=artifact.enrichments,
    )


def _validate_map_source(
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


def _validate_references(database: Path, snapshot: EvidenceSnapshot) -> None:
    with IndexStore.open_readonly(database) as index:
        chunks = {item.id: item for item in index.get_chunks()}
    for reference in snapshot.references:
        chunk = chunks.get(reference.chunk_id)
        if chunk is None or (
            chunk.content_hash,
            chunk.path,
            chunk.start_line,
            chunk.end_line,
            chunk.symbol_id,
        ) != (
            reference.content_hash,
            reference.path,
            reference.start_line,
            reference.end_line,
            reference.symbol_id,
        ):
            raise RepositoryError(
                "knowledge_map_evidence_stale",
                "Knowledge Map Evidence no longer matches the current index.",
                details={
                    "recovery_action": "rebuild_reset_recollect",
                    "retry_mode": "after_recovery",
                },
            )


def _capacity_error(message: str, *, required: int, provided: int) -> None:
    raise RepositoryError(
        "knowledge_map_evidence_capacity_exceeded",
        message,
        details={
            "provided": provided,
            "required": required,
            "recovery_action": "reset_scope_or_raise_capacity",
            "retry_mode": "after_recovery",
        },
    )


def _evidence_conflict(scope_id: str) -> None:
    raise RepositoryError(
        "knowledge_map_evidence_conflict",
        "Cited Knowledge Map Evidence must be reset before replacement.",
        details={
            "recovery_action": "reset_scope_and_recollect",
            "retry_mode": "after_recovery",
            "scope_id": scope_id,
        },
    )


def _index_changed() -> None:
    raise RepositoryError(
        "knowledge_map_index_changed",
        "Published index changed during Knowledge Map Evidence collection.",
        details={"recovery_action": "rerun_current_index", "retry_mode": "unchanged"},
    )


def _ensure_index_unchanged(
    artifact: KnowledgeMapArtifact, build_id: str, fingerprint: str
) -> None:
    if (
        artifact.source.index_build_id != build_id
        or artifact.source.repository_fingerprint != fingerprint
    ):
        _index_changed()


__all__ = [
    "EvidenceSource",
    "KnowledgeMapEvidenceService",
    "ScopeEvidenceResult",
    "validate_evidence_freshness",
]
