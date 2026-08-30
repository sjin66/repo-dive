"""Strict immutable models for public Wiki state artifacts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from math import isfinite
from pathlib import Path, PurePosixPath
from typing import cast

from repo_dive.classification.models import (
    ClassificationResult,
    classification_result_from_document,
)
from repo_dive.schema import JsonObject, JsonValue
from repo_dive.wiki.templates.models import (
    TemplateIdentity,
    template_identity_from_document,
)

WIKI_SCHEMA_VERSION = "2.0"
METADATA_SCHEMA_VERSION = "2.0"


class PageStatus(StrEnum):
    """Persisted lifecycle state for one independently generated page."""

    PENDING = "pending"
    EVIDENCE_READY = "evidence_ready"
    GENERATED = "generated"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[PageStatus, frozenset[PageStatus]] = {
    PageStatus.PENDING: frozenset({PageStatus.EVIDENCE_READY, PageStatus.FAILED}),
    PageStatus.EVIDENCE_READY: frozenset(
        {PageStatus.PENDING, PageStatus.GENERATED, PageStatus.FAILED}
    ),
    PageStatus.GENERATED: frozenset({PageStatus.PENDING, PageStatus.FAILED}),
    PageStatus.FAILED: frozenset({PageStatus.PENDING}),
}


@dataclass(frozen=True, slots=True)
class RetrievalParameters:
    """Persisted parameters needed to explain and reproduce evidence retrieval."""

    max_results: int
    strategy: str
    rrf_k: int
    channel_weights: tuple[tuple[str, float], ...]
    overlap_threshold: float

    def __post_init__(self) -> None:
        if self.max_results <= 0 or self.rrf_k < 0:
            raise ValueError("retrieval result limit and RRF k are invalid")
        _require_text(self.strategy, "retrieval strategy")
        names = tuple(name for name, _ in self.channel_weights)
        _require_unique(names, "retrieval channel names")
        if (
            not names
            or any(
                not name or name.strip() != name or not isfinite(weight) or weight < 0.0
                for name, weight in self.channel_weights
            )
            or not any(weight > 0.0 for _, weight in self.channel_weights)
        ):
            raise ValueError("retrieval channel weights are invalid")
        if not isfinite(self.overlap_threshold) or not (
            0.0 < self.overlap_threshold <= 1.0
        ):
            raise ValueError("retrieval overlap threshold is invalid")

    def to_document(self) -> JsonObject:
        return {
            "channel_weights": dict(self.channel_weights),
            "max_results": self.max_results,
            "overlap_threshold": self.overlap_threshold,
            "rrf_k": self.rrf_k,
            "strategy": self.strategy,
        }


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    """Audit metadata for one page-level evidence selection."""

    query: str
    repository_fingerprint: str
    index_schema_version: int
    index_build_id: str
    source_control: str
    source_commit: str | None
    source_dirty: bool | None
    token_budget: int
    estimated_tokens: int
    reserved_tokens: int
    estimator: str
    truncated: bool
    retrieval: RetrievalParameters
    generated_at: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.query, "evidence query"),
            (self.repository_fingerprint, "evidence repository fingerprint"),
            (self.index_build_id, "evidence index build ID"),
            (self.estimator, "evidence estimator"),
            (self.generated_at, "evidence generation timestamp"),
        ):
            _require_text(value, label)
        if self.index_schema_version <= 0 or self.token_budget <= 0:
            raise ValueError("evidence index version and budget must be positive")
        _validate_source_identity(
            self.source_control, self.source_commit, self.source_dirty
        )
        if not 0 <= self.reserved_tokens <= self.estimated_tokens <= self.token_budget:
            raise ValueError("evidence token accounting is invalid")

    def to_document(self) -> JsonObject:
        return {
            "estimated_tokens": self.estimated_tokens,
            "estimator": self.estimator,
            "generated_at": self.generated_at,
            "index_build_id": self.index_build_id,
            "index_schema_version": self.index_schema_version,
            "query": self.query,
            "repository_fingerprint": self.repository_fingerprint,
            "source_commit": self.source_commit,
            "source_control": self.source_control,
            "source_dirty": self.source_dirty,
            "reserved_tokens": self.reserved_tokens,
            "retrieval": self.retrieval.to_document(),
            "token_budget": self.token_budget,
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """Stable reference from a Wiki page to complete repository evidence."""

    evidence_id: str
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    content_hash: str | None = None
    role: str = "supplemental"
    subsection_ids: tuple[str, ...] = ()
    direct_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.evidence_id, "evidence ID")
        _require_text(self.chunk_id, "Chunk ID")
        _validate_repository_path(self.path)
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("Evidence line range must be one-based and inclusive")
        if self.content_hash is not None:
            _require_text(self.content_hash, "Evidence content hash")
        if self.role not in {"direct", "supplemental"}:
            raise ValueError("Evidence role must be direct or supplemental")
        _require_unique(self.subsection_ids, "Evidence Subsection IDs")
        _require_unique(self.direct_paths, "Evidence direct paths")
        for path in self.direct_paths:
            _validate_repository_path(path)
        if self.role == "direct" and (not self.subsection_ids or not self.direct_paths):
            raise ValueError("direct Evidence requires Subsection and path coverage")
        if self.role == "direct" and any(
            path != self.path for path in self.direct_paths
        ):
            raise ValueError("direct Evidence path coverage must match its Chunk path")
        if self.role == "supplemental" and (self.subsection_ids or self.direct_paths):
            raise ValueError("supplemental Evidence cannot declare direct coverage")

    def to_document(self) -> JsonObject:
        return {
            "chunk_id": self.chunk_id,
            "content_hash": self.content_hash,
            "end_line": self.end_line,
            "evidence_id": self.evidence_id,
            "path": self.path,
            "role": self.role,
            "start_line": self.start_line,
            "subsection_ids": list(self.subsection_ids),
            "direct_paths": list(self.direct_paths),
        }


@dataclass(frozen=True, slots=True)
class Subsection:
    """Immutable generation and direct-Evidence contract below one Page."""

    id: str
    title: str
    description: str
    direct_source_paths: tuple[str, ...]
    documentation_only: bool = False

    def __post_init__(self) -> None:
        _require_logical_id(self.id, "Subsection ID")
        _require_text(self.title, "Subsection title")
        _require_text(self.description, "Subsection description")
        _require_unique(self.direct_source_paths, "Subsection direct source paths")
        for path in self.direct_source_paths:
            _validate_repository_path(path)
        if not self.documentation_only and not self.direct_source_paths:
            raise ValueError(
                "non-documentation Subsections require direct source paths"
            )

    def to_document(self) -> JsonObject:
        return {
            "description": self.description,
            "direct_source_paths": list(self.direct_source_paths),
            "documentation_only": self.documentation_only,
            "id": self.id,
            "title": self.title,
        }


@dataclass(frozen=True, slots=True)
class SubsectionContent:
    """One caller fragment and its citations, persisted atomically with its Page."""

    subsection_id: str
    body: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_logical_id(self.subsection_id, "Subsection content ID")
        if not self.body.strip():
            raise ValueError("Subsection body must not be empty")
        if not self.evidence_ids:
            raise ValueError("Subsection citations must not be empty")
        _require_unique(self.evidence_ids, "Subsection citation Evidence IDs")

    def to_document(self) -> JsonObject:
        return {
            "body": self.body,
            "evidence_ids": list(self.evidence_ids),
            "subsection_id": self.subsection_id,
        }


@dataclass(frozen=True, slots=True)
class Page:
    """One independently retrievable and generatable Wiki page."""

    id: str
    title: str
    description: str
    status: PageStatus
    relevant_files: tuple[str, ...] = ()
    related_page_ids: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    evidence_snapshot: EvidenceSnapshot | None = None
    citation_ids: tuple[str, ...] = ()
    body: str | None = None
    error: str | None = None
    subsections: tuple[Subsection, ...] = ()
    subsection_contents: tuple[SubsectionContent, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.id, "page ID")
        _require_text(self.title, "page title")
        _require_text(self.description, "page description")
        if not isinstance(self.status, PageStatus):
            raise ValueError("page status is invalid")
        _require_unique(self.relevant_files, "relevant file paths")
        for path in self.relevant_files:
            _validate_repository_path(path)
        _require_unique(self.related_page_ids, "related page IDs")
        if self.id in self.related_page_ids:
            raise ValueError("a page cannot relate to itself")
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        _require_unique(evidence_ids, "Evidence IDs")
        _require_unique(self.citation_ids, "citation Evidence IDs")
        if set(self.citation_ids) - set(evidence_ids):
            raise ValueError("citation Evidence IDs must belong to the page")
        if self.evidence_snapshot is not None and (
            not self.evidence
            or any(item.content_hash is None for item in self.evidence)
        ):
            raise ValueError("evidence snapshot requires hashed Evidence references")
        if self.body is not None and not self.body:
            raise ValueError("page body must not be empty when present")
        if self.error is not None:
            _require_text(self.error, "page error")
        subsection_ids = tuple(item.id for item in self.subsections)
        _require_unique(subsection_ids, "Page Subsection IDs")
        content_ids = tuple(item.subsection_id for item in self.subsection_contents)
        _require_unique(content_ids, "Page Subsection content IDs")
        if self.subsection_contents and content_ids != subsection_ids:
            raise ValueError(
                "Subsection content order must exactly match the Page contract"
            )
        content_citations = {
            evidence_id
            for content in self.subsection_contents
            for evidence_id in content.evidence_ids
        }
        if content_citations - set(evidence_ids):
            raise ValueError("Subsection citations must belong to the page")
        subsection_paths = {
            subsection.id: set(subsection.direct_source_paths)
            for subsection in self.subsections
        }
        for reference in self.evidence:
            if any(
                subsection_id not in subsection_paths
                or reference.path not in subsection_paths[subsection_id]
                for subsection_id in reference.subsection_ids
            ):
                raise ValueError(
                    "direct Evidence coverage must match the Page contract"
                )

    def transition_to(self, target: PageStatus) -> Page:
        """Return a new Page after validating one explicit lifecycle step."""
        if (
            not isinstance(target, PageStatus)
            or target not in _ALLOWED_TRANSITIONS[self.status]
        ):
            target_value = (
                target.value if isinstance(target, PageStatus) else str(target)
            )
            raise ValueError(
                f"page transition from {self.status.value} to {target_value} is invalid"
            )
        return replace(self, status=target)

    def to_document(self) -> JsonObject:
        return {
            "body": self.body,
            "citation_ids": list(self.citation_ids),
            "description": self.description,
            "error": self.error,
            "evidence": [item.to_document() for item in self.evidence],
            "evidence_snapshot": (
                self.evidence_snapshot.to_document()
                if self.evidence_snapshot is not None
                else None
            ),
            "id": self.id,
            "related_page_ids": list(self.related_page_ids),
            "relevant_files": list(self.relevant_files),
            "status": self.status.value,
            "title": self.title,
            "subsections": [item.to_document() for item in self.subsections],
            "subsection_contents": [
                item.to_document() for item in self.subsection_contents
            ],
        }


@dataclass(frozen=True, slots=True)
class Section:
    """An ordered group of Wiki pages."""

    id: str
    title: str
    pages: tuple[Page, ...]

    def __post_init__(self) -> None:
        _require_text(self.id, "section ID")
        _require_text(self.title, "section title")
        if not self.pages:
            raise ValueError("section pages must not be empty")
        _require_unique(tuple(page.id for page in self.pages), "section page IDs")

    def to_document(self) -> JsonObject:
        return {
            "id": self.id,
            "pages": [page.to_document() for page in self.pages],
            "title": self.title,
        }


@dataclass(frozen=True, slots=True)
class Wiki:
    """Complete ordered Wiki structure and resumable page state."""

    title: str
    description: str
    sections: tuple[Section, ...]
    schema_version: str = WIKI_SCHEMA_VERSION
    framework_labels: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != WIKI_SCHEMA_VERSION:
            raise ValueError("Wiki schema version is not supported")
        _require_text(self.title, "Wiki title")
        _require_text(self.description, "Wiki description")
        if not self.sections:
            raise ValueError("Wiki sections must not be empty")
        _require_unique(
            tuple(section.id for section in self.sections), "Wiki section IDs"
        )
        pages = tuple(page for section in self.sections for page in section.pages)
        page_ids = tuple(page.id for page in pages)
        _require_unique(page_ids, "Wiki page IDs")
        known_page_ids = set(page_ids)
        for page in pages:
            unknown = set(page.related_page_ids) - known_page_ids
            if unknown:
                raise ValueError("related page IDs must reference Wiki pages")
        label_keys = tuple(key for key, _ in self.framework_labels)
        _require_unique(label_keys, "framework label IDs")

    def to_document(self) -> JsonObject:
        return {
            "description": self.description,
            "schema_version": self.schema_version,
            "sections": [section.to_document() for section in self.sections],
            "title": self.title,
            "framework_labels": dict(self.framework_labels),
        }


@dataclass(frozen=True, slots=True)
class Metadata:
    """Repository and index identity for the public Wiki state."""

    repository: str
    repository_fingerprint: str
    source_commit: str | None
    output_language: str
    index_schema_version: int
    index_build_id: str
    created_at: str
    updated_at: str
    wiki_schema_version: str = WIKI_SCHEMA_VERSION
    schema_version: str = METADATA_SCHEMA_VERSION
    source_control: str = "non_git"
    source_dirty: bool | None = None
    repository_classification: ClassificationResult | None = None
    template: TemplateIdentity | None = None

    def __post_init__(self) -> None:
        if self.schema_version != METADATA_SCHEMA_VERSION:
            raise ValueError("Metadata schema version is not supported")
        if self.wiki_schema_version != WIKI_SCHEMA_VERSION:
            raise ValueError("Metadata Wiki schema version is not supported")
        _require_text(self.repository, "metadata repository")
        if not Path(self.repository).is_absolute():
            raise ValueError("metadata repository must be an absolute path")
        _require_text(self.repository_fingerprint, "repository fingerprint")
        _validate_source_identity(
            self.source_control, self.source_commit, self.source_dirty
        )
        _require_text(self.output_language, "output language")
        if self.index_schema_version <= 0:
            raise ValueError("index schema version must be positive")
        _require_text(self.index_build_id, "index build ID")
        _require_text(self.created_at, "created timestamp")
        _require_text(self.updated_at, "updated timestamp")
        if (self.repository_classification is None) != (self.template is None):
            raise ValueError(
                "classification and template governance identities must be paired"
            )
        if self.repository_classification is not None:
            classification = self.repository_classification
            if (
                classification.repository_fingerprint != self.repository_fingerprint
                or classification.index_build_id != self.index_build_id
            ):
                raise ValueError(
                    "classification identity must match the persisted index identity"
                )
            if self.template is None or (
                self.template.primary_id != classification.effective_primary.id
                or self.template.topology_id != classification.topology.id
                or self.template.facets
                != tuple(item.id for item in classification.facets)
                or self.template.locale != self.output_language
            ):
                raise ValueError(
                    "template identity must match classification and locale"
                )

    def to_document(self) -> JsonObject:
        return {
            "created_at": self.created_at,
            "index_build_id": self.index_build_id,
            "index_schema_version": self.index_schema_version,
            "output_language": self.output_language,
            "repository": self.repository,
            "repository_fingerprint": self.repository_fingerprint,
            "schema_version": self.schema_version,
            "source_commit": self.source_commit,
            "source_control": self.source_control,
            "source_dirty": self.source_dirty,
            "updated_at": self.updated_at,
            "wiki_schema_version": self.wiki_schema_version,
            "repository_classification": (
                self.repository_classification.to_document()
                if self.repository_classification is not None
                else None
            ),
            "template": self.template.to_document()
            if self.template is not None
            else None,
        }


def wiki_from_document(document: JsonObject) -> Wiki:
    """Strictly decode one untrusted Wiki state document."""
    _require_fields(
        document,
        {"description", "framework_labels", "schema_version", "sections", "title"},
        "Wiki document fields",
    )
    wiki = Wiki(
        title=_string(document["title"]),
        description=_string(document["description"]),
        sections=tuple(
            _section_from_document(_object(item))
            for item in _array(document["sections"])
        ),
        schema_version=_string(document["schema_version"]),
        framework_labels=_string_items(_object(document["framework_labels"])),
    )
    if not wiki.framework_labels or any(
        not page.subsections for section in wiki.sections for page in section.pages
    ):
        raise ValueError(
            "Schema 2.0 requires locale labels and at least one Subsection per Page"
        )
    return wiki


def metadata_from_document(document: JsonObject) -> Metadata:
    """Strictly decode one untrusted Wiki metadata document."""
    _require_fields(
        document,
        {
            "created_at",
            "index_build_id",
            "index_schema_version",
            "output_language",
            "repository",
            "repository_classification",
            "repository_fingerprint",
            "schema_version",
            "source_commit",
            "source_control",
            "source_dirty",
            "template",
            "updated_at",
            "wiki_schema_version",
        },
        "Metadata document fields",
    )
    metadata = Metadata(
        repository=_string(document["repository"]),
        repository_fingerprint=_string(document["repository_fingerprint"]),
        source_commit=_optional_string(document["source_commit"]),
        source_control=_string(document["source_control"]),
        source_dirty=_optional_boolean(document["source_dirty"]),
        output_language=_string(document["output_language"]),
        index_schema_version=_integer(document["index_schema_version"]),
        index_build_id=_string(document["index_build_id"]),
        created_at=_string(document["created_at"]),
        updated_at=_string(document["updated_at"]),
        wiki_schema_version=_string(document["wiki_schema_version"]),
        schema_version=_string(document["schema_version"]),
        repository_classification=(
            classification_result_from_document(
                _object(document["repository_classification"])
            )
            if document["repository_classification"] is not None
            else None
        ),
        template=(
            template_identity_from_document(_object(document["template"]))
            if document["template"] is not None
            else None
        ),
    )
    if metadata.source_control == "non_git" and (
        metadata.source_commit is not None or metadata.source_dirty is not None
    ):
        raise ValueError("non-Git metadata cannot declare Git source identity")
    if metadata.source_control == "git" and metadata.source_dirty is None:
        raise ValueError("Git metadata requires a dirty-worktree state")
    return metadata


def _section_from_document(document: JsonObject) -> Section:
    _require_fields(document, {"id", "pages", "title"}, "Section document fields")
    return Section(
        id=_string(document["id"]),
        title=_string(document["title"]),
        pages=tuple(
            _page_from_document(_object(item)) for item in _array(document["pages"])
        ),
    )


def _page_from_document(document: JsonObject) -> Page:
    _require_optional_fields(
        document,
        {
            "body",
            "description",
            "error",
            "evidence",
            "id",
            "related_page_ids",
            "relevant_files",
            "status",
            "title",
            "subsections",
            "subsection_contents",
        },
        {"citation_ids", "evidence_snapshot"},
        "Page document fields",
    )
    return Page(
        id=_string(document["id"]),
        title=_string(document["title"]),
        description=_string(document["description"]),
        status=PageStatus(_string(document["status"])),
        relevant_files=_string_tuple(document["relevant_files"]),
        related_page_ids=_string_tuple(document["related_page_ids"]),
        evidence=tuple(
            _evidence_from_document(_object(item))
            for item in _array(document["evidence"])
        ),
        evidence_snapshot=_optional_evidence_snapshot(
            document.get("evidence_snapshot")
        ),
        citation_ids=_string_tuple(document.get("citation_ids", [])),
        body=_optional_string(document["body"]),
        error=_optional_string(document["error"]),
        subsections=tuple(
            _subsection_from_document(_object(item))
            for item in _array(document["subsections"])
        ),
        subsection_contents=tuple(
            _subsection_content_from_document(_object(item))
            for item in _array(document["subsection_contents"])
        ),
    )


def _evidence_from_document(document: JsonObject) -> EvidenceRef:
    _require_optional_fields(
        document,
        {"chunk_id", "end_line", "evidence_id", "path", "start_line"},
        {"content_hash", "direct_paths", "role", "subsection_ids"},
        "Evidence document fields",
    )
    return EvidenceRef(
        evidence_id=_string(document["evidence_id"]),
        chunk_id=_string(document["chunk_id"]),
        path=_string(document["path"]),
        start_line=_integer(document["start_line"]),
        end_line=_integer(document["end_line"]),
        content_hash=_optional_string(document.get("content_hash")),
        role=_string(document.get("role", "supplemental")),
        subsection_ids=_string_tuple(document.get("subsection_ids", [])),
        direct_paths=_string_tuple(document.get("direct_paths", [])),
    )


def _subsection_from_document(document: JsonObject) -> Subsection:
    _require_fields(
        document,
        {"description", "direct_source_paths", "documentation_only", "id", "title"},
        "Subsection document fields",
    )
    return Subsection(
        id=_string(document["id"]),
        title=_string(document["title"]),
        description=_string(document["description"]),
        direct_source_paths=_string_tuple(document["direct_source_paths"]),
        documentation_only=_boolean(document["documentation_only"]),
    )


def _subsection_content_from_document(document: JsonObject) -> SubsectionContent:
    _require_fields(
        document,
        {"body", "evidence_ids", "subsection_id"},
        "Subsection content document fields",
    )
    return SubsectionContent(
        subsection_id=_string(document["subsection_id"]),
        body=_string(document["body"]),
        evidence_ids=_string_tuple(document["evidence_ids"]),
    )


def _optional_evidence_snapshot(value: JsonValue | None) -> EvidenceSnapshot | None:
    if value is None:
        return None
    document = _object(value)
    _require_fields(
        document,
        {
            "estimated_tokens",
            "estimator",
            "generated_at",
            "index_build_id",
            "index_schema_version",
            "query",
            "repository_fingerprint",
            "reserved_tokens",
            "retrieval",
            "source_commit",
            "source_control",
            "source_dirty",
            "token_budget",
            "truncated",
        },
        "Evidence snapshot fields",
    )
    return EvidenceSnapshot(
        query=_string(document["query"]),
        repository_fingerprint=_string(document["repository_fingerprint"]),
        index_schema_version=_integer(document["index_schema_version"]),
        index_build_id=_string(document["index_build_id"]),
        source_control=_string(document["source_control"]),
        source_commit=_optional_string(document["source_commit"]),
        source_dirty=_optional_boolean(document["source_dirty"]),
        token_budget=_integer(document["token_budget"]),
        estimated_tokens=_integer(document["estimated_tokens"]),
        reserved_tokens=_integer(document["reserved_tokens"]),
        estimator=_string(document["estimator"]),
        truncated=_boolean(document["truncated"]),
        retrieval=_retrieval_parameters(_object(document["retrieval"])),
        generated_at=_string(document["generated_at"]),
    )


def _retrieval_parameters(document: JsonObject) -> RetrievalParameters:
    _require_fields(
        document,
        {
            "channel_weights",
            "max_results",
            "overlap_threshold",
            "rrf_k",
            "strategy",
        },
        "Retrieval parameter fields",
    )
    weights = _object(document["channel_weights"])
    if not all(type(value) in {int, float} for value in weights.values()):
        raise TypeError("retrieval channel weights must be numbers")
    return RetrievalParameters(
        max_results=_integer(document["max_results"]),
        strategy=_string(document["strategy"]),
        rrf_k=_integer(document["rrf_k"]),
        channel_weights=tuple(
            (name, float(cast(int | float, weight))) for name, weight in weights.items()
        ),
        overlap_threshold=_number(document["overlap_threshold"]),
    )


def _require_text(value: str, label: str) -> None:
    if not value or value.strip() != value:
        raise ValueError(f"{label} must not be empty or padded")


def _validate_source_identity(
    source_control: str, source_commit: str | None, source_dirty: bool | None
) -> None:
    if source_control not in {"git", "non_git"}:
        raise ValueError("source control must be git or non_git")
    if source_control == "non_git" and (
        source_commit is not None or source_dirty is not None
    ):
        raise ValueError("non-Git state cannot declare Git source identity")
    if source_control == "git" and source_dirty is None:
        raise ValueError("Git state requires a dirty-worktree state")
    if source_commit is not None and (
        len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise ValueError("source commit must be a full lowercase Git object ID")


def _require_logical_id(value: str, label: str) -> None:
    _require_text(value, label)
    if not value[0].islower() or any(
        not (character.islower() or character.isdigit() or character == "_")
        for character in value
    ):
        raise ValueError(f"{label} must be lower snake case")


def _require_unique(values: tuple[str, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _validate_repository_path(path: str) -> None:
    candidate = PurePosixPath(path)
    if (
        not path
        or "\\" in path
        or candidate.is_absolute()
        or ".." in candidate.parts
        or candidate.as_posix() != path
        or path == "."
    ):
        raise ValueError("path must be a repository-relative POSIX path")


def _require_fields(document: JsonObject, expected: set[str], label: str) -> None:
    if set(document) != expected:
        raise ValueError(f"{label} are invalid")


def _require_optional_fields(
    document: JsonObject,
    required: set[str],
    optional: set[str],
    label: str,
) -> None:
    if not required <= set(document) or set(document) - required - optional:
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


def _optional_string(value: JsonValue) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise TypeError("value must be a string or null")


def _string_tuple(value: JsonValue) -> tuple[str, ...]:
    items = _array(value)
    if not all(isinstance(item, str) for item in items):
        raise TypeError("value must contain only strings")
    return tuple(cast(list[str], items))


def _integer(value: JsonValue) -> int:
    if type(value) is not int:
        raise TypeError("value must be an integer")
    return value


def _number(value: JsonValue) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("value must be a number")
    return float(value)


def _boolean(value: JsonValue) -> bool:
    if not isinstance(value, bool):
        raise TypeError("value must be a boolean")
    return value


def _optional_boolean(value: JsonValue) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise TypeError("value must be a boolean or null")


def _string_items(document: JsonObject) -> tuple[tuple[str, str], ...]:
    if not all(isinstance(value, str) for value in document.values()):
        raise TypeError("value must contain only string values")
    return tuple((key, cast(str, value)) for key, value in sorted(document.items()))


__all__ = [
    "METADATA_SCHEMA_VERSION",
    "WIKI_SCHEMA_VERSION",
    "EvidenceRef",
    "EvidenceSnapshot",
    "Metadata",
    "Page",
    "PageStatus",
    "RetrievalParameters",
    "Section",
    "Subsection",
    "SubsectionContent",
    "Wiki",
    "metadata_from_document",
    "wiki_from_document",
]
