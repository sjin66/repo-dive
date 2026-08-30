"""Bounded read-only adapter over one validated published index generation."""

from __future__ import annotations

import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import PublishedIndex
from repo_dive.indexing.store import IndexStore
from repo_dive.knowledge_map.models import LanguageCoverage, MapCoverage, MapSource
from repo_dive.parsing.models import (
    Chunk,
    Relationship,
    Symbol,
    create_chunk,
    create_relationship,
    create_symbol,
)
from repo_dive.scanner.models import FileRecord, ReadStatus

_PAGE_SIZE = 256


@dataclass(frozen=True, slots=True)
class IndexSnapshot:
    """Immutable timestamp-free source facts for deterministic map derivation."""

    source: MapSource
    files: tuple[FileRecord, ...]
    symbols: tuple[Symbol, ...]
    relationships: tuple[Relationship, ...]
    coverage: MapCoverage
    script_entrypoints: tuple[str, ...] = ()


def snapshot_from_published_index(
    published: PublishedIndex,
    *,
    source_fact_budget: int,
) -> IndexSnapshot:
    """Read a complete stable inventory or fail before returning partial facts."""
    if source_fact_budget <= 0:
        raise ValueError("source fact budget must be positive")
    manifest = published.manifest
    required = (
        manifest.counts.files
        + manifest.counts.chunks
        + manifest.counts.symbols
        + manifest.counts.relationships
    )
    if required > source_fact_budget:
        raise RepositoryError(
            "knowledge_map_source_budget_exceeded",
            "Published source facts exceed the Knowledge Map source budget.",
            details={
                "actual": required,
                "budget": source_fact_budget,
                "recovery_action": "raise_source_budget_or_reduce_scope",
                "retry_mode": "after_recovery",
            },
        )

    files: list[FileRecord] = []
    symbols: list[Symbol] = []
    relationships: list[Relationship] = []
    chunk_ids_by_path: dict[str, tuple[str, ...]] = {}
    script_entrypoints: set[str] = set()
    observations: set[str] = set()
    with IndexStore.open_readonly(published.database) as store:
        cursor: str | None = None
        while True:
            page = store.page_files(after_path=cursor, limit=_PAGE_SIZE)
            if not page:
                break
            files.extend(page)
            cursor = page[-1].path
        for file in files:
            parsed = store.get_parse_result(file.path)
            if (
                any(not _chunk_has_valid_identity(chunk) for chunk in parsed.chunks)
                or any(
                    not _symbol_has_valid_identity(symbol) for symbol in parsed.symbols
                )
                or any(
                    not _relationship_has_valid_identity(relationship)
                    for relationship in parsed.relationships
                )
            ):
                _raise_manifest_database_mismatch(published)
            symbols.extend(parsed.symbols)
            relationships.extend(parsed.relationships)
            if file.path == "pyproject.toml":
                manifest_text = _reconstruct_text(parsed.chunks)
                if (
                    file.size_bytes > 65_536
                    or len(manifest_text.encode("utf-8")) > 65_536
                ):
                    observations.add("manifest_oversized")
                else:
                    try:
                        manifest_document = tomllib.loads(manifest_text)
                        scripts = manifest_document.get("project", {}).get(
                            "scripts", {}
                        )
                        if type(scripts) is not dict or any(
                            type(value) is not str for value in scripts.values()
                        ):
                            raise ValueError("project scripts are invalid")
                        script_entrypoints.update(
                            value.replace(":", ".", 1) for value in scripts.values()
                        )
                        if scripts:
                            observations.add("pyproject_scripts_present")
                    except (tomllib.TOMLDecodeError, AttributeError, ValueError):
                        observations.add("manifest_malformed")
            chunks: list[str] = []
            ordinal = -1
            while True:
                chunk_page = store.page_chunk_ids(
                    file.path,
                    after_ordinal=ordinal,
                    limit=_PAGE_SIZE,
                )
                if not chunk_page:
                    break
                chunks.extend(chunk_id for _, chunk_id in chunk_page)
                ordinal = chunk_page[-1][0]
            chunk_ids_by_path[file.path] = tuple(chunks)

    ordered_symbols = tuple(
        sorted(symbols, key=lambda item: (item.path, item.start_line, item.id))
    )
    ordered_relationships = tuple(
        sorted(
            relationships,
            key=lambda item: (
                item.path,
                item.start_line,
                item.end_line,
                item.occurrence_discriminator,
                item.id,
            ),
        )
    )
    _verify_manifest_counts(
        published,
        files,
        chunk_ids_by_path,
        ordered_symbols,
        ordered_relationships,
    )
    language_counts = Counter(file.language for file in files)
    relationship_counts = Counter(item.kind for item in ordered_relationships)
    symbols_by_language: Counter[str] = Counter()
    relationships_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    language_by_path = {file.path: file.language for file in files}
    for symbol in ordered_symbols:
        symbols_by_language[language_by_path[symbol.path]] += 1
    for relationship in ordered_relationships:
        relationships_by_language[language_by_path[relationship.path]][
            relationship.kind
        ] += 1
    parser_coverage = tuple(
        LanguageCoverage(
            language=language,
            file_count=count,
            indexed_file_count=sum(
                file.status is ReadStatus.READ and file.language == language
                for file in files
            ),
            symbol_count=symbols_by_language[language],
            relationship_count=sum(relationships_by_language[language].values()),
            relationship_kinds=tuple(
                sorted(relationships_by_language[language].items())
            ),
            graph_capability=(
                "full"
                if language == "python"
                else "containment_only"
                if language in {"javascript", "typescript"}
                else "none"
            ),
        )
        for language, count in sorted(language_counts.items())
    )
    coverage = MapCoverage(
        total_files=len(files),
        indexed_files=sum(file.status is ReadStatus.READ for file in files),
        skipped_files=sum(file.status is not ReadStatus.READ for file in files),
        symbols=len(ordered_symbols),
        relationship_occurrences=len(ordered_relationships),
        languages=tuple(sorted(language_counts.items())),
        relationship_kinds=tuple(sorted(relationship_counts.items())),
        parser_coverage=parser_coverage,
        observations=tuple(sorted(observations)),
    )
    source = MapSource(
        repository_fingerprint=manifest.repository_fingerprint,
        index_build_id=manifest.build_id,
        index_schema_version=manifest.parameters.index_schema_version,
        source_control=manifest.source_control,
        source_commit=manifest.source_commit,
        source_dirty=manifest.source_dirty,
    )
    return IndexSnapshot(
        source=source,
        files=tuple(files),
        symbols=ordered_symbols,
        relationships=ordered_relationships,
        coverage=coverage,
        script_entrypoints=tuple(sorted(script_entrypoints)),
    )


def _verify_manifest_counts(
    published: PublishedIndex,
    files: list[FileRecord],
    chunk_ids_by_path: dict[str, tuple[str, ...]],
    symbols: tuple[Symbol, ...],
    relationships: tuple[Relationship, ...],
) -> None:
    counts = published.manifest.counts
    manifest_by_path = {item.path: item for item in published.manifest.files}
    if (
        len(files) != counts.files
        or sum(len(value) for value in chunk_ids_by_path.values()) != counts.chunks
        or len(symbols) != counts.symbols
        or len(relationships) != counts.relationships
        or tuple(file.path for file in files)
        != tuple(item.path for item in published.manifest.files)
        or any(
            file.content_hash != manifest_by_path[file.path].content_hash
            or file.status.value != manifest_by_path[file.path].status
            or chunk_ids_by_path[file.path] != manifest_by_path[file.path].chunk_ids
            for file in files
        )
    ):
        _raise_manifest_database_mismatch(published)


def _raise_manifest_database_mismatch(published: PublishedIndex) -> None:
    raise RepositoryError(
        "index_manifest_database_mismatch",
        "Published index Manifest does not match its database.",
        details={"build_id": published.manifest.build_id},
    )


def _reconstruct_text(chunks: tuple[Chunk, ...]) -> str:
    lines: dict[int, str] = {}
    for chunk in chunks:
        for number, text in enumerate(
            chunk.text.splitlines(keepends=True), chunk.start_line
        ):
            lines.setdefault(number, text)
    return "".join(
        lines.get(number, "\n") for number in range(1, max(lines, default=0) + 1)
    )


def _chunk_has_valid_identity(chunk: Chunk) -> bool:
    return (
        create_chunk(
            path=chunk.path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            text=chunk.text,
            symbol_id=chunk.symbol_id,
        )
        == chunk
    )


def _symbol_has_valid_identity(symbol: Symbol) -> bool:
    return (
        create_symbol(
            kind=symbol.kind,
            name=symbol.name,
            qualified_name=symbol.qualified_name,
            path=symbol.path,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
        )
        == symbol
    )


def _relationship_has_valid_identity(relationship: Relationship) -> bool:
    return (
        create_relationship(
            source_id=relationship.source_id,
            target_id=relationship.target_id,
            kind=relationship.kind,
            confidence=relationship.confidence,
            provenance=relationship.provenance,
            path=relationship.path,
            start_line=relationship.start_line,
            end_line=relationship.end_line,
            occurrence_discriminator=relationship.occurrence_discriminator,
        )
        == relationship
    )
