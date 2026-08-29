from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from repo_dive.classification.adapter import snapshot_from_published_index
from repo_dive.errors import RepositoryError
from repo_dive.indexing.manifest import (
    BuildParameters,
    IndexCounts,
    IndexManifest,
    ManifestFile,
)
from repo_dive.indexing.service import PublishedIndex
from repo_dive.indexing.store import IndexStore
from repo_dive.parsing.models import ParseResult, create_chunk
from repo_dive.scanner.models import FileRecord, ReadStatus, SourceFile


def test_adapter_reads_only_published_index_records_in_stable_order(
    tmp_path: Path,
) -> None:
    database = tmp_path / "index.sqlite3"
    sources = (
        SourceFile(
            FileRecord("z.txt", "text", 1, "z", "utf-8", ReadStatus.READ, None), "z"
        ),
        SourceFile(
            FileRecord("package.json", "json", 2, "a", "utf-8", ReadStatus.READ, None),
            "{}",
        ),
    )
    with IndexStore.initialize(database) as store:
        chunk_ids: dict[str, tuple[str, ...]] = {}
        for source in sources:
            assert source.text is not None
            parsed = ParseResult(
                chunks=(
                    create_chunk(
                        path=source.record.path,
                        start_line=1,
                        end_line=1,
                        text=source.text,
                    ),
                )
            )
            store.replace_document(source, parsed)
            chunk_ids[source.record.path] = tuple(chunk.id for chunk in parsed.chunks)
    manifest = IndexManifest(
        build_id="build-1",
        repository_fingerprint="fingerprint-1",
        scan_mode="filesystem",
        parameters=BuildParameters(),
        files=tuple(
            ManifestFile(path, hash_, "read", chunk_ids[path])
            for path, hash_ in (("package.json", "a"), ("z.txt", "z"))
        ),
        counts=IndexCounts(
            files=2,
            indexed_files=2,
            skipped_files=0,
            chunks=2,
            symbols=0,
            relationships=0,
        ),
    )

    result = snapshot_from_published_index(PublishedIndex(tmp_path, manifest, database))

    assert [item.path for item in result.files] == ["package.json", "z.txt"]
    assert result.files[0].text == "{}"
    assert result.repository_fingerprint == "fingerprint-1"


def test_adapter_rejects_manifest_metadata_that_disagrees_with_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "index.sqlite3"
    source = SourceFile(
        FileRecord(
            "package.json", "json", 2, "database-hash", "utf-8", ReadStatus.READ, None
        ),
        "{}",
    )
    parsed = ParseResult(
        chunks=(create_chunk(path="package.json", start_line=1, end_line=1, text="{}"),)
    )
    with IndexStore.initialize(database) as store:
        store.replace_document(source, parsed)
    manifest = IndexManifest(
        build_id="build-1",
        repository_fingerprint="fingerprint-1",
        scan_mode="filesystem",
        parameters=BuildParameters(),
        files=(
            ManifestFile(
                "package.json",
                "different-hash",
                "read",
                tuple(chunk.id for chunk in parsed.chunks),
            ),
        ),
        counts=IndexCounts(1, 1, 0, 1, 0, 0),
    )

    with pytest.raises(RepositoryError) as exc_info:
        snapshot_from_published_index(PublishedIndex(tmp_path, manifest, database))

    assert exc_info.value.code == "index_manifest_database_mismatch"


def test_adapter_rejects_tampered_manifest_chunk_content(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    source = SourceFile(
        FileRecord(
            "package.json", "json", 2, "source-hash", "utf-8", ReadStatus.READ, None
        ),
        "{}",
    )
    parsed = ParseResult(
        chunks=(create_chunk(path="package.json", start_line=1, end_line=1, text="{}"),)
    )
    with IndexStore.initialize(database) as store:
        store.replace_document(source, parsed)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE chunks SET text = ?", ('{"private": true}',))
    manifest = IndexManifest(
        build_id="build-1",
        repository_fingerprint="fingerprint-1",
        scan_mode="filesystem",
        parameters=BuildParameters(),
        files=(
            ManifestFile(
                "package.json",
                "source-hash",
                "read",
                tuple(chunk.id for chunk in parsed.chunks),
            ),
        ),
        counts=IndexCounts(1, 1, 0, 1, 0, 0),
    )

    with pytest.raises(RepositoryError) as exc_info:
        snapshot_from_published_index(PublishedIndex(tmp_path, manifest, database))

    assert exc_info.value.code == "index_manifest_database_mismatch"


def test_adapter_reports_manifest_database_mismatch_as_repository_error(
    tmp_path: Path,
) -> None:
    database = tmp_path / "index.sqlite3"
    with IndexStore.initialize(database):
        pass
    manifest = IndexManifest(
        build_id="build-1",
        repository_fingerprint="fingerprint-1",
        scan_mode="filesystem",
        parameters=BuildParameters(),
        files=(ManifestFile("missing.json", "hash", "read", ()),),
        counts=IndexCounts(
            files=1,
            indexed_files=1,
            skipped_files=0,
            chunks=0,
            symbols=0,
            relationships=0,
        ),
    )

    with pytest.raises(RepositoryError) as exc_info:
        snapshot_from_published_index(PublishedIndex(tmp_path, manifest, database))

    assert exc_info.value.code == "index_manifest_database_mismatch"
