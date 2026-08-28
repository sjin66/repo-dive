"""Application service for strict Wiki structure and resumable status."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from repo_dive.context import EvidenceBundle, EvidencePacker
from repo_dive.errors import InvocationError, RepositoryError
from repo_dive.indexing.service import PublishedIndex, load_published_index
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION
from repo_dive.parsing.models import Symbol
from repo_dive.retrieval.fusion import FusionMetadata
from repo_dive.retrieval.service import search_repository
from repo_dive.schema import JsonObject, JsonValue
from repo_dive.wiki.models import (
    METADATA_SCHEMA_VERSION,
    EvidenceRef,
    EvidenceSnapshot,
    Metadata,
    Page,
    PageStatus,
    RetrievalParameters,
    Section,
    Wiki,
)
from repo_dive.wiki.store import WikiStore
from repo_dive.wiki.validation import stale_page_ids_for_index

STRUCTURE_SCHEMA_VERSION = "1.0"
MAX_EVIDENCE_QUERY_LENGTH = 1_000


@dataclass(frozen=True, slots=True)
class StructurePage:
    """Caller-owned structural fields for one page, excluding persisted state."""

    id: str
    title: str
    description: str
    relevant_files: tuple[str, ...]
    related_page_ids: tuple[str, ...]

    def to_pending_page(self) -> Page:
        """Validate structure through the canonical persisted Page model."""
        return Page(
            id=self.id,
            title=self.title,
            description=self.description,
            status=PageStatus.PENDING,
            relevant_files=self.relevant_files,
            related_page_ids=self.related_page_ids,
        )


@dataclass(frozen=True, slots=True)
class StructureSection:
    """Caller-owned ordered section structure."""

    id: str
    title: str
    pages: tuple[StructurePage, ...]

    def to_pending_section(self) -> Section:
        return Section(
            id=self.id,
            title=self.title,
            pages=tuple(page.to_pending_page() for page in self.pages),
        )


@dataclass(frozen=True, slots=True)
class WikiStructure:
    """Strict external structure proposal without mutable lifecycle fields."""

    title: str
    description: str
    output_language: str
    sections: tuple[StructureSection, ...]
    schema_version: str = STRUCTURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != STRUCTURE_SCHEMA_VERSION:
            raise ValueError("Wiki structure schema version is not supported")
        if (
            not self.output_language
            or self.output_language.strip() != self.output_language
        ):
            raise ValueError("output language must not be empty or padded")
        self.to_pending_wiki()

    def to_pending_wiki(self) -> Wiki:
        return Wiki(
            title=self.title,
            description=self.description,
            sections=tuple(section.to_pending_section() for section in self.sections),
        )


@dataclass(frozen=True, slots=True)
class StructureUpdate:
    """Observable outcome of applying one validated structure proposal."""

    changed: bool
    created_page_ids: tuple[str, ...]
    invalidated_page_ids: tuple[str, ...]
    preserved_page_ids: tuple[str, ...]
    wiki: Wiki
    metadata: Metadata


@dataclass(frozen=True, slots=True)
class WikiState:
    """A complete, mutually present Wiki and metadata snapshot."""

    wiki: Wiki
    metadata: Metadata


@dataclass(frozen=True, slots=True)
class WikiEvidenceUpdate:
    """Persisted page Evidence plus complete source output for the caller."""

    page: Page
    bundle: EvidenceBundle
    fusion: FusionMetadata
    symbols: tuple[Symbol, ...]
    metadata: Metadata


class WikiService:
    """Validate, merge, persist, and inspect repository-owned Wiki state."""

    def __init__(
        self,
        repository: str | Path,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._store = WikiStore(repository)
        self._clock = clock or _utc_now

    def apply_structure(self, structure: WikiStructure) -> StructureUpdate:
        """Apply a structure while preserving state for unaffected Page IDs."""
        published = load_published_index(self._store.repository)
        proposed = structure.to_pending_wiki()
        _validate_relevant_files(proposed, published)
        current = self._read_optional_state()
        now = self._clock()

        if current is None:
            metadata = _new_metadata(
                published,
                output_language=structure.output_language,
                timestamp=now,
            )
            self._store.write_metadata(metadata)
            self._store.write_wiki(proposed)
            return StructureUpdate(
                changed=True,
                created_page_ids=_page_ids(proposed),
                invalidated_page_ids=(),
                preserved_page_ids=(),
                wiki=proposed,
                metadata=metadata,
            )

        language_changed = current.metadata.output_language != structure.output_language
        index_changed = (
            current.metadata.repository_fingerprint
            != published.manifest.repository_fingerprint
            or current.metadata.index_build_id != published.manifest.build_id
            or current.metadata.index_schema_version != INDEX_SCHEMA_VERSION
        )
        stale_ids = (
            frozenset(stale_page_ids_for_index(published, current.wiki))
            if index_changed
            else frozenset()
        )
        merged, created, invalidated, preserved = _merge_wiki(
            current.wiki,
            proposed,
            stale_page_ids=stale_ids,
            invalidate_all=language_changed,
        )
        metadata_changed = (
            current.metadata.repository != str(published.repository)
            or current.metadata.repository_fingerprint
            != published.manifest.repository_fingerprint
            or current.metadata.output_language != structure.output_language
            or current.metadata.index_schema_version != INDEX_SCHEMA_VERSION
            or current.metadata.index_build_id != published.manifest.build_id
        )
        changed = merged != current.wiki or metadata_changed
        if not changed:
            return StructureUpdate(
                changed=False,
                created_page_ids=(),
                invalidated_page_ids=(),
                preserved_page_ids=_page_ids(current.wiki),
                wiki=current.wiki,
                metadata=current.metadata,
            )

        metadata = replace(
            current.metadata,
            repository=str(published.repository),
            repository_fingerprint=published.manifest.repository_fingerprint,
            output_language=structure.output_language,
            index_schema_version=INDEX_SCHEMA_VERSION,
            index_build_id=published.manifest.build_id,
            updated_at=now,
        )
        self._store.write_metadata(metadata)
        self._store.write_wiki(merged)
        return StructureUpdate(
            changed=True,
            created_page_ids=created,
            invalidated_page_ids=invalidated,
            preserved_page_ids=preserved,
            wiki=merged,
            metadata=metadata,
        )

    def read_state(self) -> WikiState:
        """Read a complete initialized state or return a stable repository error."""
        state = self._read_optional_state()
        if state is None:
            raise RepositoryError(
                "wiki_not_initialized",
                "Repository Wiki has not been initialized.",
            )
        return state

    def collect_evidence(
        self,
        page_id: str,
        *,
        token_budget: int,
        max_results: int,
    ) -> WikiEvidenceUpdate:
        """Retrieve, persist, then return one page's complete Evidence bundle."""
        state = self.read_state()
        page = _find_page(state.wiki, page_id)
        if page is None:
            raise InvocationError(
                "wiki_page_unknown",
                "Wiki page ID does not exist in the current structure.",
                details={"page_id": page_id},
            )

        try:
            query = _evidence_query(page)
            retrieved = search_repository(
                self._store.repository,
                query,
                max_results=max_results,
            )
            published = load_published_index(self._store.repository)
            if retrieved.build_id != published.manifest.build_id:
                raise RepositoryError(
                    "index_changed_during_operation",
                    "Repository index changed while Evidence was being collected.",
                )
            bundle = EvidencePacker().pack(
                query,
                retrieved.fusion.hits,
                token_budget=token_budget,
            )
            if not bundle.items:
                raise RepositoryError(
                    "wiki_evidence_empty",
                    "No complete repository Evidence fits the page budget.",
                    details={"page_id": page_id},
                )
            stale_ids = stale_page_ids_for_index(published, state.wiki)
        except RepositoryError as error:
            self._persist_failed_page(state, page_id=page_id, error_code=error.code)
            raise

        generated_at = self._clock()
        snapshot = EvidenceSnapshot(
            query=query,
            repository_fingerprint=published.manifest.repository_fingerprint,
            index_schema_version=INDEX_SCHEMA_VERSION,
            index_build_id=published.manifest.build_id,
            token_budget=bundle.token_budget,
            estimated_tokens=bundle.estimated_tokens,
            reserved_tokens=bundle.reserved_tokens,
            estimator=bundle.estimator,
            truncated=bundle.truncated,
            retrieval=RetrievalParameters(
                max_results=max_results,
                strategy=retrieved.fusion.metadata.strategy,
                rrf_k=retrieved.fusion.metadata.rrf_k,
                channel_weights=retrieved.fusion.metadata.channel_weights,
                overlap_threshold=retrieved.fusion.metadata.overlap_threshold,
            ),
            generated_at=generated_at,
        )
        references = tuple(
            EvidenceRef(
                evidence_id=item.evidence_id,
                chunk_id=item.hit.chunk.id,
                path=item.hit.chunk.path,
                start_line=item.hit.chunk.start_line,
                end_line=item.hit.chunk.end_line,
                content_hash=item.hit.chunk.content_hash,
            )
            for item in bundle.items
        )
        normalized = _reset_stale_pages(state.wiki, frozenset(stale_ids))
        current_page = _find_page(normalized, page_id)
        if current_page is None:  # pragma: no cover - protected by immutable IDs
            raise RuntimeError("Wiki page disappeared while collecting Evidence")
        updated_page = _with_ready_evidence(
            current_page,
            evidence=references,
            snapshot=snapshot,
        )
        updated_wiki = _replace_page(normalized, updated_page)
        metadata = _updated_metadata(
            state.metadata,
            published,
            timestamp=generated_at,
        )
        self._store.write_metadata(metadata)
        self._store.write_wiki(updated_wiki)
        return WikiEvidenceUpdate(
            page=updated_page,
            bundle=bundle,
            fusion=retrieved.fusion.metadata,
            symbols=retrieved.symbols,
            metadata=metadata,
        )

    def _persist_failed_page(
        self,
        state: WikiState,
        *,
        page_id: str,
        error_code: str,
    ) -> None:
        page = _find_page(state.wiki, page_id)
        if page is None:
            return
        failed = (
            page
            if page.status is PageStatus.FAILED
            else page.transition_to(PageStatus.FAILED)
        )
        failed = replace(failed, error=error_code)
        timestamp = self._clock()
        self._store.write_metadata(replace(state.metadata, updated_at=timestamp))
        self._store.write_wiki(_replace_page(state.wiki, failed))

    def _read_optional_state(self) -> WikiState | None:
        has_wiki = self._store.has_wiki()
        has_metadata = self._store.has_metadata()
        if not has_wiki and not has_metadata:
            return None
        if has_wiki != has_metadata:
            raise RepositoryError(
                "wiki_state_incomplete",
                "Repository Wiki state is incomplete.",
            )
        return WikiState(
            wiki=self._store.read_wiki(),
            metadata=self._store.read_metadata(),
        )


def structure_from_document(document: JsonObject) -> WikiStructure:
    """Strictly decode a caller-provided stateless Wiki structure."""
    _require_fields(
        document,
        {
            "description",
            "output_language",
            "schema_version",
            "sections",
            "title",
        },
        "Wiki structure fields",
    )
    return WikiStructure(
        title=_string(document["title"]),
        description=_string(document["description"]),
        output_language=_string(document["output_language"]),
        sections=tuple(
            _section_from_document(_object(item))
            for item in _array(document["sections"])
        ),
        schema_version=_string(document["schema_version"]),
    )


def _section_from_document(document: JsonObject) -> StructureSection:
    _require_fields(document, {"id", "pages", "title"}, "Section fields")
    return StructureSection(
        id=_string(document["id"]),
        title=_string(document["title"]),
        pages=tuple(
            _page_from_document(_object(item)) for item in _array(document["pages"])
        ),
    )


def _page_from_document(document: JsonObject) -> StructurePage:
    _require_fields(
        document,
        {
            "description",
            "id",
            "related_page_ids",
            "relevant_files",
            "title",
        },
        "Page structure fields",
    )
    return StructurePage(
        id=_string(document["id"]),
        title=_string(document["title"]),
        description=_string(document["description"]),
        relevant_files=_string_tuple(document["relevant_files"]),
        related_page_ids=_string_tuple(document["related_page_ids"]),
    )


def _validate_relevant_files(wiki: Wiki, published: PublishedIndex) -> None:
    known_paths = {item.path for item in published.manifest.files}
    requested_paths = {
        path
        for section in wiki.sections
        for page in section.pages
        for path in page.relevant_files
    }
    unknown = tuple(sorted(requested_paths - known_paths))
    if unknown:
        raise InvocationError(
            "wiki_relevant_file_unknown",
            "Wiki structure references files outside the current index.",
            details={"paths": list(unknown)},
        )


def _merge_wiki(
    current: Wiki,
    proposed: Wiki,
    *,
    stale_page_ids: frozenset[str],
    invalidate_all: bool,
) -> tuple[Wiki, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    current_pages = {
        page.id: page for section in current.sections for page in section.pages
    }
    created: list[str] = []
    invalidated: list[str] = []
    preserved: list[str] = []
    sections: list[Section] = []
    for proposed_section in proposed.sections:
        pages: list[Page] = []
        for proposed_page in proposed_section.pages:
            previous = current_pages.get(proposed_page.id)
            if previous is None:
                created.append(proposed_page.id)
                pages.append(proposed_page)
            elif (
                not invalidate_all
                and proposed_page.id not in stale_page_ids
                and _same_page_structure(previous, proposed_page)
            ):
                preserved.append(proposed_page.id)
                pages.append(previous)
            else:
                invalidated.append(proposed_page.id)
                pages.append(
                    replace(
                        proposed_page,
                        status=PageStatus.PENDING,
                        evidence=previous.evidence,
                        body=previous.body,
                        error=previous.error,
                    )
                )
        sections.append(replace(proposed_section, pages=tuple(pages)))
    return (
        replace(proposed, sections=tuple(sections)),
        tuple(created),
        tuple(invalidated),
        tuple(preserved),
    )


def _same_page_structure(current: Page, proposed: Page) -> bool:
    return (
        current.id == proposed.id
        and current.title == proposed.title
        and current.description == proposed.description
        and current.relevant_files == proposed.relevant_files
        and current.related_page_ids == proposed.related_page_ids
    )


def _new_metadata(
    published: PublishedIndex,
    *,
    output_language: str,
    timestamp: str,
) -> Metadata:
    return Metadata(
        repository=str(published.repository),
        repository_fingerprint=published.manifest.repository_fingerprint,
        source_commit=None,
        output_language=output_language,
        index_schema_version=INDEX_SCHEMA_VERSION,
        index_build_id=published.manifest.build_id,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _updated_metadata(
    current: Metadata,
    published: PublishedIndex,
    *,
    timestamp: str,
) -> Metadata:
    return replace(
        current,
        repository=str(published.repository),
        repository_fingerprint=published.manifest.repository_fingerprint,
        index_schema_version=INDEX_SCHEMA_VERSION,
        index_build_id=published.manifest.build_id,
        updated_at=timestamp,
    )


def _evidence_query(page: Page) -> str:
    query = "\n".join(
        (
            page.title,
            page.description,
            *(f"path:{path}" for path in page.relevant_files),
        )
    )
    if len(query) > MAX_EVIDENCE_QUERY_LENGTH:
        raise RepositoryError(
            "wiki_evidence_query_too_large",
            "Wiki page retrieval query exceeds the supported size.",
            details={
                "max_characters": MAX_EVIDENCE_QUERY_LENGTH,
                "page_id": page.id,
            },
        )
    return query


def _find_page(wiki: Wiki, page_id: str) -> Page | None:
    return next(
        (
            page
            for section in wiki.sections
            for page in section.pages
            if page.id == page_id
        ),
        None,
    )


def _replace_page(wiki: Wiki, replacement: Page) -> Wiki:
    return replace(
        wiki,
        sections=tuple(
            replace(
                section,
                pages=tuple(
                    replacement if page.id == replacement.id else page
                    for page in section.pages
                ),
            )
            for section in wiki.sections
        ),
    )


def _reset_stale_pages(wiki: Wiki, stale_ids: frozenset[str]) -> Wiki:
    return replace(
        wiki,
        sections=tuple(
            replace(
                section,
                pages=tuple(
                    page.transition_to(PageStatus.PENDING)
                    if page.id in stale_ids
                    and page.status in {PageStatus.EVIDENCE_READY, PageStatus.GENERATED}
                    else page
                    for page in section.pages
                ),
            )
            for section in wiki.sections
        ),
    )


def _with_ready_evidence(
    page: Page,
    *,
    evidence: tuple[EvidenceRef, ...],
    snapshot: EvidenceSnapshot,
) -> Page:
    pending = (
        page
        if page.status is PageStatus.PENDING
        else page.transition_to(PageStatus.PENDING)
    )
    return replace(
        pending.transition_to(PageStatus.EVIDENCE_READY),
        evidence=evidence,
        evidence_snapshot=snapshot,
        error=None,
    )


def _page_ids(wiki: Wiki) -> tuple[str, ...]:
    return tuple(page.id for section in wiki.sections for page in section.pages)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_fields(document: JsonObject, expected: set[str], label: str) -> None:
    if set(document) != expected:
        raise ValueError(f"{label} are invalid")


def _object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("value must be an object")
    return value


def _array(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError("value must be an array")
    return value


def _string(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    return value


def _string_tuple(value: JsonValue) -> tuple[str, ...]:
    items = _array(value)
    if not all(isinstance(item, str) for item in items):
        raise TypeError("value must contain only strings")
    return tuple(cast(list[str], items))


__all__ = [
    "METADATA_SCHEMA_VERSION",
    "STRUCTURE_SCHEMA_VERSION",
    "MAX_EVIDENCE_QUERY_LENGTH",
    "StructureUpdate",
    "WikiService",
    "WikiEvidenceUpdate",
    "WikiState",
    "WikiStructure",
    "structure_from_document",
]
