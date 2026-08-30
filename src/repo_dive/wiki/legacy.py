"""Deprecated Schema 1.0 structure persistence isolated from governed Wiki state."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import cast

from repo_dive.errors import InvocationError, RepositoryError
from repo_dive.indexing.service import PublishedIndex, load_published_index
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION
from repo_dive.schema import JsonObject, JsonValue
from repo_dive.storage.atomic import atomic_write_json
from repo_dive.storage.paths import resolve_repository, resolve_within_repository
from repo_dive.wiki.store import METADATA_PATH, WIKI_PATH

LEGACY_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class LegacyPage:
    id: str
    title: str
    description: str
    relevant_files: tuple[str, ...]
    related_page_ids: tuple[str, ...]
    status: str = "pending"
    evidence: tuple[JsonObject, ...] = ()
    evidence_snapshot: JsonObject | None = None
    citation_ids: tuple[str, ...] = ()
    body: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        _text(self.id)
        _text(self.title)
        _text(self.description)
        _unique(self.relevant_files)
        _unique(self.related_page_ids)
        for path in self.relevant_files:
            _path(path)
        if self.id in self.related_page_ids:
            raise ValueError("a legacy Page cannot relate to itself")

    def to_document(self) -> JsonObject:
        return {
            "body": self.body,
            "citation_ids": list(self.citation_ids),
            "description": self.description,
            "error": self.error,
            "evidence": list(self.evidence),
            "evidence_snapshot": self.evidence_snapshot,
            "id": self.id,
            "related_page_ids": list(self.related_page_ids),
            "relevant_files": list(self.relevant_files),
            "status": self.status,
            "title": self.title,
        }


@dataclass(frozen=True, slots=True)
class LegacySection:
    id: str
    title: str
    pages: tuple[LegacyPage, ...]

    def __post_init__(self) -> None:
        _text(self.id)
        _text(self.title)
        if not self.pages:
            raise ValueError("legacy Section pages must not be empty")
        _unique(tuple(page.id for page in self.pages))

    def to_document(self) -> JsonObject:
        return {
            "id": self.id,
            "pages": [page.to_document() for page in self.pages],
            "title": self.title,
        }


@dataclass(frozen=True, slots=True)
class LegacyWiki:
    title: str
    description: str
    sections: tuple[LegacySection, ...]
    schema_version: str = LEGACY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != LEGACY_SCHEMA_VERSION:
            raise ValueError("legacy Wiki version is unsupported")
        _text(self.title)
        _text(self.description)
        if not self.sections:
            raise ValueError("legacy Wiki sections must not be empty")
        _unique(tuple(section.id for section in self.sections))
        pages = tuple(page for section in self.sections for page in section.pages)
        page_ids = tuple(page.id for page in pages)
        _unique(page_ids)
        known = set(page_ids)
        if any(set(page.related_page_ids) - known for page in pages):
            raise ValueError("legacy related Page IDs must reference the Wiki")

    def to_document(self) -> JsonObject:
        return {
            "description": self.description,
            "schema_version": self.schema_version,
            "sections": [section.to_document() for section in self.sections],
            "title": self.title,
        }


@dataclass(frozen=True, slots=True)
class LegacyMetadata:
    repository: str
    repository_fingerprint: str
    output_language: str
    index_build_id: str
    created_at: str
    updated_at: str
    source_commit: str | None
    index_schema_version: int = INDEX_SCHEMA_VERSION
    wiki_schema_version: str = LEGACY_SCHEMA_VERSION
    schema_version: str = LEGACY_SCHEMA_VERSION

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


@dataclass(frozen=True, slots=True)
class LegacyStructure:
    title: str
    description: str
    output_language: str
    sections: tuple[LegacySection, ...]

    def to_wiki(self) -> LegacyWiki:
        return LegacyWiki(self.title, self.description, self.sections)


@dataclass(frozen=True, slots=True)
class LegacyStructureUpdate:
    changed: bool
    created_page_ids: tuple[str, ...]
    invalidated_page_ids: tuple[str, ...]
    preserved_page_ids: tuple[str, ...]
    wiki: LegacyWiki
    metadata: LegacyMetadata


class LegacyWikiService:
    """Persist only deprecated Schema 1.0 structure artifacts."""

    def __init__(
        self,
        repository: str | Path,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.repository = resolve_repository(repository)
        self._clock = clock or _utc_now

    def apply_structure(self, structure: LegacyStructure) -> LegacyStructureUpdate:
        published = load_published_index(self.repository)
        proposed = structure.to_wiki()
        _validate_files(proposed, published)
        current = self._read_optional()
        timestamp = self._clock()
        if current is None:
            metadata = _metadata(published, structure.output_language, timestamp)
            self._write(proposed, metadata)
            return LegacyStructureUpdate(
                True, _page_ids(proposed), (), (), proposed, metadata
            )
        current_wiki, current_metadata = current
        merged, created, invalidated, preserved = _merge(current_wiki, proposed)
        metadata_changed = (
            current_metadata.repository_fingerprint
            != published.manifest.repository_fingerprint
            or current_metadata.index_build_id != published.manifest.build_id
            or current_metadata.output_language != structure.output_language
        )
        if merged == current_wiki and not metadata_changed:
            return LegacyStructureUpdate(
                False, (), (), _page_ids(current_wiki), current_wiki, current_metadata
            )
        metadata = LegacyMetadata(
            repository=str(published.repository),
            repository_fingerprint=published.manifest.repository_fingerprint,
            output_language=structure.output_language,
            index_build_id=published.manifest.build_id,
            created_at=current_metadata.created_at,
            updated_at=timestamp,
            source_commit=published.manifest.source_commit,
        )
        self._write(merged, metadata)
        return LegacyStructureUpdate(
            True, created, invalidated, preserved, merged, metadata
        )

    def _read_optional(self) -> tuple[LegacyWiki, LegacyMetadata] | None:
        wiki_path = resolve_within_repository(self.repository, WIKI_PATH)
        metadata_path = resolve_within_repository(self.repository, METADATA_PATH)
        if not wiki_path.exists() and not metadata_path.exists():
            return None
        if not wiki_path.exists() or not metadata_path.exists():
            raise RepositoryError(
                "wiki_state_incomplete", "Repository Wiki state is incomplete."
            )
        try:
            return _read_wiki(wiki_path), _read_metadata(metadata_path)
        except RepositoryError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise RepositoryError(
                "wiki_state_invalid", "Repository Wiki state is invalid."
            ) from error

    def _write(self, wiki: LegacyWiki, metadata: LegacyMetadata) -> None:
        atomic_write_json(self.repository, METADATA_PATH, metadata.to_document())
        atomic_write_json(self.repository, WIKI_PATH, wiki.to_document())


def has_legacy_state(repository: str | Path) -> bool:
    """Return whether both public state files identify deprecated Schema 1.0."""
    root = resolve_repository(repository)
    wiki_path = resolve_within_repository(root, WIKI_PATH)
    metadata_path = resolve_within_repository(root, METADATA_PATH)
    if not wiki_path.exists() or not metadata_path.exists():
        return False
    try:
        wiki = json.loads(wiki_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(wiki, dict)
        and wiki.get("schema_version") == LEGACY_SCHEMA_VERSION
        and isinstance(metadata, dict)
        and metadata.get("schema_version") == LEGACY_SCHEMA_VERSION
        and metadata.get("wiki_schema_version") == LEGACY_SCHEMA_VERSION
    )


def legacy_structure_from_document(document: JsonObject) -> LegacyStructure:
    _fields(
        document,
        {"description", "output_language", "schema_version", "sections", "title"},
    )
    if _string(document["schema_version"]) != LEGACY_SCHEMA_VERSION:
        raise ValueError("legacy structure version is unsupported")
    return LegacyStructure(
        _string(document["title"]),
        _string(document["description"]),
        _string(document["output_language"]),
        tuple(
            _section(_object(item), structure=True)
            for item in _array(document["sections"])
        ),
    )


def _read_wiki(path: Path) -> LegacyWiki:
    document = _load(path)
    if document.get("schema_version") != LEGACY_SCHEMA_VERSION:
        raise RepositoryError(
            "wiki_state_version_unsupported",
            "Repository Wiki state version is not supported.",
            details={
                "actual": document.get("schema_version"),
                "expected": LEGACY_SCHEMA_VERSION,
            },
        )
    _fields(document, {"description", "schema_version", "sections", "title"})
    return LegacyWiki(
        _string(document["title"]),
        _string(document["description"]),
        tuple(
            _section(_object(item), structure=False)
            for item in _array(document["sections"])
        ),
        _string(document["schema_version"]),
    )


def _read_metadata(path: Path) -> LegacyMetadata:
    document = _load(path)
    if (
        document.get("schema_version") != LEGACY_SCHEMA_VERSION
        or document.get("wiki_schema_version") != LEGACY_SCHEMA_VERSION
    ):
        raise RepositoryError(
            "wiki_state_version_unsupported",
            "Repository Wiki state version is not supported.",
            details={
                "expected": LEGACY_SCHEMA_VERSION,
                "metadata_schema_version": document.get("schema_version"),
                "wiki_schema_version": document.get("wiki_schema_version"),
            },
        )
    _fields(
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
    )
    return LegacyMetadata(
        repository=_string(document["repository"]),
        repository_fingerprint=_string(document["repository_fingerprint"]),
        output_language=_string(document["output_language"]),
        index_build_id=_string(document["index_build_id"]),
        created_at=_string(document["created_at"]),
        updated_at=_string(document["updated_at"]),
        source_commit=_optional_string(document["source_commit"]),
        index_schema_version=_integer(document["index_schema_version"]),
        wiki_schema_version=_string(document["wiki_schema_version"]),
        schema_version=_string(document["schema_version"]),
    )


def _section(document: JsonObject, *, structure: bool) -> LegacySection:
    _fields(document, {"id", "pages", "title"})
    return LegacySection(
        _string(document["id"]),
        _string(document["title"]),
        tuple(
            _page(_object(item), structure=structure)
            for item in _array(document["pages"])
        ),
    )


def _page(document: JsonObject, *, structure: bool) -> LegacyPage:
    structure_fields = {
        "description",
        "id",
        "related_page_ids",
        "relevant_files",
        "title",
    }
    state_fields = structure_fields | {
        "body",
        "citation_ids",
        "error",
        "evidence",
        "evidence_snapshot",
        "status",
    }
    _fields(document, structure_fields if structure else state_fields)
    return LegacyPage(
        id=_string(document["id"]),
        title=_string(document["title"]),
        description=_string(document["description"]),
        relevant_files=_strings(document["relevant_files"]),
        related_page_ids=_strings(document["related_page_ids"]),
        status="pending" if structure else _string(document["status"]),
        evidence=()
        if structure
        else tuple(_object(item) for item in _array(document["evidence"])),
        evidence_snapshot=None
        if structure
        else _optional_object(document["evidence_snapshot"]),
        citation_ids=() if structure else _strings(document["citation_ids"]),
        body=None if structure else _optional_string(document["body"]),
        error=None if structure else _optional_string(document["error"]),
    )


def _merge(
    current: LegacyWiki, proposed: LegacyWiki
) -> tuple[LegacyWiki, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    previous = {page.id: page for section in current.sections for page in section.pages}
    created: list[str] = []
    invalidated: list[str] = []
    preserved: list[str] = []
    sections: list[LegacySection] = []
    for section in proposed.sections:
        pages: list[LegacyPage] = []
        for page in section.pages:
            old = previous.get(page.id)
            if old is None:
                created.append(page.id)
                pages.append(page)
            elif _same_structure(old, page):
                preserved.append(page.id)
                pages.append(old)
            else:
                invalidated.append(page.id)
                pages.append(
                    LegacyPage(
                        page.id,
                        page.title,
                        page.description,
                        page.relevant_files,
                        page.related_page_ids,
                        body=old.body,
                        error=old.error,
                    )
                )
        sections.append(LegacySection(section.id, section.title, tuple(pages)))
    return (
        LegacyWiki(proposed.title, proposed.description, tuple(sections)),
        tuple(created),
        tuple(invalidated),
        tuple(preserved),
    )


def _same_structure(first: LegacyPage, second: LegacyPage) -> bool:
    return (
        first.id,
        first.title,
        first.description,
        first.relevant_files,
        first.related_page_ids,
    ) == (
        second.id,
        second.title,
        second.description,
        second.relevant_files,
        second.related_page_ids,
    )


def _validate_files(wiki: LegacyWiki, published: PublishedIndex) -> None:
    known = {item.path for item in published.manifest.files}
    requested = {
        path
        for section in wiki.sections
        for page in section.pages
        for path in page.relevant_files
    }
    unknown = tuple(sorted(requested - known))
    if unknown:
        raise InvocationError(
            "wiki_relevant_file_unknown",
            "Wiki structure references files outside the current index.",
            details={"paths": list(unknown)},
        )


def _metadata(
    published: PublishedIndex, language: str, timestamp: str
) -> LegacyMetadata:
    return LegacyMetadata(
        str(published.repository),
        published.manifest.repository_fingerprint,
        language,
        published.manifest.build_id,
        timestamp,
        timestamp,
        published.manifest.source_commit,
    )


def _page_ids(wiki: LegacyWiki) -> tuple[str, ...]:
    return tuple(page.id for section in wiki.sections for page in section.pages)


def _load(path: Path) -> JsonObject:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as error:
        raise RepositoryError(
            "wiki_state_invalid", "Repository Wiki state is invalid."
        ) from error


def _fields(document: JsonObject, expected: set[str]) -> None:
    if set(document) != expected:
        raise ValueError("legacy document fields are invalid")


def _text(value: str) -> None:
    if not value or value.strip() != value:
        raise ValueError("legacy text must not be empty or padded")


def _unique(values: tuple[str, ...]) -> None:
    if len(values) != len(set(values)):
        raise ValueError("legacy values must be unique")


def _path(value: str) -> None:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
    ):
        raise ValueError("legacy path must be repository-relative POSIX")


def _object(value: JsonValue | object) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("legacy value must be an object")
    return cast(JsonObject, value)


def _optional_object(value: JsonValue) -> JsonObject | None:
    return None if value is None else _object(value)


def _array(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError("legacy value must be an array")
    return value


def _string(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise TypeError("legacy value must be a string")
    return value


def _optional_string(value: JsonValue) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise TypeError("legacy value must be a string or null")


def _strings(value: JsonValue) -> tuple[str, ...]:
    values = _array(value)
    if not all(isinstance(item, str) for item in values):
        raise TypeError("legacy array must contain strings")
    return tuple(cast(list[str], values))


def _integer(value: JsonValue) -> int:
    if type(value) is not int:
        raise TypeError("legacy value must be an integer")
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


__all__ = [
    "LEGACY_SCHEMA_VERSION",
    "LegacyStructureUpdate",
    "LegacyWikiService",
    "has_legacy_state",
    "legacy_structure_from_document",
]
