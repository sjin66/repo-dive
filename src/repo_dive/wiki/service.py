"""Application service for strict Wiki structure and resumable status."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from repo_dive.errors import InvocationError, RepositoryError
from repo_dive.indexing.service import PublishedIndex, load_published_index
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION
from repo_dive.schema import JsonObject, JsonValue
from repo_dive.wiki.models import (
    METADATA_SCHEMA_VERSION,
    Metadata,
    Page,
    PageStatus,
    Section,
    Wiki,
)
from repo_dive.wiki.store import WikiStore

STRUCTURE_SCHEMA_VERSION = "1.0"


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

        source_changed = (
            current.metadata.repository_fingerprint
            != published.manifest.repository_fingerprint
            or current.metadata.index_build_id != published.manifest.build_id
            or current.metadata.index_schema_version != INDEX_SCHEMA_VERSION
        )
        language_changed = current.metadata.output_language != structure.output_language
        merged, created, invalidated, preserved = _merge_wiki(
            current.wiki,
            proposed,
            invalidate_all=source_changed or language_changed,
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
            elif not invalidate_all and _same_page_structure(previous, proposed_page):
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
    "StructureUpdate",
    "WikiService",
    "WikiState",
    "WikiStructure",
    "structure_from_document",
]
