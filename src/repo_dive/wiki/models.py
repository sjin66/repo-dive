"""Strict immutable models for public Wiki state artifacts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import cast

from repo_dive.schema import JsonObject, JsonValue

WIKI_SCHEMA_VERSION = "1.0"
METADATA_SCHEMA_VERSION = "1.0"


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
class EvidenceRef:
    """Stable reference from a Wiki page to complete repository evidence."""

    evidence_id: str
    chunk_id: str
    path: str
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        _require_text(self.evidence_id, "evidence ID")
        _require_text(self.chunk_id, "Chunk ID")
        _validate_repository_path(self.path)
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("Evidence line range must be one-based and inclusive")

    def to_document(self) -> JsonObject:
        return {
            "chunk_id": self.chunk_id,
            "end_line": self.end_line,
            "evidence_id": self.evidence_id,
            "path": self.path,
            "start_line": self.start_line,
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
    body: str | None = None
    error: str | None = None

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
        if self.body is not None and not self.body:
            raise ValueError("page body must not be empty when present")
        if self.error is not None:
            _require_text(self.error, "page error")

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
            "description": self.description,
            "error": self.error,
            "evidence": [item.to_document() for item in self.evidence],
            "id": self.id,
            "related_page_ids": list(self.related_page_ids),
            "relevant_files": list(self.relevant_files),
            "status": self.status.value,
            "title": self.title,
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

    def to_document(self) -> JsonObject:
        return {
            "description": self.description,
            "schema_version": self.schema_version,
            "sections": [section.to_document() for section in self.sections],
            "title": self.title,
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

    def __post_init__(self) -> None:
        if self.schema_version != METADATA_SCHEMA_VERSION:
            raise ValueError("Metadata schema version is not supported")
        if self.wiki_schema_version != WIKI_SCHEMA_VERSION:
            raise ValueError("Metadata Wiki schema version is not supported")
        _require_text(self.repository, "metadata repository")
        if not Path(self.repository).is_absolute():
            raise ValueError("metadata repository must be an absolute path")
        _require_text(self.repository_fingerprint, "repository fingerprint")
        if self.source_commit is not None:
            _require_text(self.source_commit, "source commit")
        _require_text(self.output_language, "output language")
        if self.index_schema_version <= 0:
            raise ValueError("index schema version must be positive")
        _require_text(self.index_build_id, "index build ID")
        _require_text(self.created_at, "created timestamp")
        _require_text(self.updated_at, "updated timestamp")

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
            "updated_at": self.updated_at,
            "wiki_schema_version": self.wiki_schema_version,
        }


def wiki_from_document(document: JsonObject) -> Wiki:
    """Strictly decode one untrusted Wiki state document."""
    _require_fields(
        document,
        {"description", "schema_version", "sections", "title"},
        "Wiki document fields",
    )
    return Wiki(
        title=_string(document["title"]),
        description=_string(document["description"]),
        sections=tuple(
            _section_from_document(_object(item))
            for item in _array(document["sections"])
        ),
        schema_version=_string(document["schema_version"]),
    )


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
            "repository_fingerprint",
            "schema_version",
            "source_commit",
            "updated_at",
            "wiki_schema_version",
        },
        "Metadata document fields",
    )
    return Metadata(
        repository=_string(document["repository"]),
        repository_fingerprint=_string(document["repository_fingerprint"]),
        source_commit=_optional_string(document["source_commit"]),
        output_language=_string(document["output_language"]),
        index_schema_version=_integer(document["index_schema_version"]),
        index_build_id=_string(document["index_build_id"]),
        created_at=_string(document["created_at"]),
        updated_at=_string(document["updated_at"]),
        wiki_schema_version=_string(document["wiki_schema_version"]),
        schema_version=_string(document["schema_version"]),
    )


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
    _require_fields(
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
        },
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
        body=_optional_string(document["body"]),
        error=_optional_string(document["error"]),
    )


def _evidence_from_document(document: JsonObject) -> EvidenceRef:
    _require_fields(
        document,
        {"chunk_id", "end_line", "evidence_id", "path", "start_line"},
        "Evidence document fields",
    )
    return EvidenceRef(
        evidence_id=_string(document["evidence_id"]),
        chunk_id=_string(document["chunk_id"]),
        path=_string(document["path"]),
        start_line=_integer(document["start_line"]),
        end_line=_integer(document["end_line"]),
    )


def _require_text(value: str, label: str) -> None:
    if not value or value.strip() != value:
        raise ValueError(f"{label} must not be empty or padded")


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


__all__ = [
    "METADATA_SCHEMA_VERSION",
    "WIKI_SCHEMA_VERSION",
    "EvidenceRef",
    "Metadata",
    "Page",
    "PageStatus",
    "Section",
    "Wiki",
    "metadata_from_document",
    "wiki_from_document",
]
