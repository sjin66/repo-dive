"""Read-only adapter from a validated published index to classifier evidence."""

from __future__ import annotations

from typing import NoReturn

from repo_dive.classification.models import (
    MAX_MANIFEST_BYTES,
    IndexedFile,
    IndexSnapshot,
)
from repo_dive.classification.registry import (
    BUILTIN_REGISTRY,
    NamedManifestKeyValue,
    RuleRegistry,
)
from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import PublishedIndex
from repo_dive.indexing.store import IndexStore
from repo_dive.parsing.models import Chunk, create_chunk
from repo_dive.scanner.models import ReadStatus


def snapshot_from_published_index(
    published: PublishedIndex, *, registry: RuleRegistry = BUILTIN_REGISTRY
) -> IndexSnapshot:
    """Load only persisted file metadata and indexed text from one publication."""
    files: list[IndexedFile] = []
    named_paths = {
        rule.matcher.path
        for rule in registry.signals
        if isinstance(rule.matcher, NamedManifestKeyValue)
    }
    with IndexStore.open_readonly(published.database) as store:
        for manifest_file in published.manifest.files:
            record = store.get_file(manifest_file.path)
            if (
                record is None
                or record.status.value != manifest_file.status
                or record.content_hash != manifest_file.content_hash
            ):
                _raise_manifest_database_mismatch(published, manifest_file.path)
            text = None
            if (
                record.status is ReadStatus.READ
                and record.path in named_paths
                and record.size_bytes <= MAX_MANIFEST_BYTES
            ):
                parsed = store.get_parse_result(record.path)
                if tuple(
                    chunk.id for chunk in parsed.chunks
                ) != manifest_file.chunk_ids or any(
                    not _chunk_has_valid_identity(chunk) for chunk in parsed.chunks
                ):
                    _raise_manifest_database_mismatch(published, manifest_file.path)
                text = _reconstruct_text(parsed.chunks)
            files.append(
                IndexedFile(
                    path=record.path,
                    language=record.language,
                    readable=record.status is ReadStatus.READ,
                    size_bytes=record.size_bytes,
                    text=text,
                )
            )
    return IndexSnapshot(
        repository_fingerprint=published.manifest.repository_fingerprint,
        index_build_id=published.manifest.build_id,
        files=tuple(files),
    )


def _raise_manifest_database_mismatch(published: PublishedIndex, path: str) -> NoReturn:
    raise RepositoryError(
        "index_manifest_database_mismatch",
        "Repository index Manifest does not match its database.",
        details={"build_id": published.manifest.build_id, "path": path},
    )


def _reconstruct_text(chunks: tuple[Chunk, ...]) -> str:
    if not chunks:
        return ""
    lines: dict[int, str] = {}
    for chunk in chunks:
        for number, text in enumerate(
            chunk.text.splitlines(keepends=True), chunk.start_line
        ):
            lines.setdefault(number, text)
    if not lines:
        return ""
    return "".join(lines.get(number, "\n") for number in range(1, max(lines) + 1))


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
