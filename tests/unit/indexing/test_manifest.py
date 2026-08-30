from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.indexing.manifest import (
    BuildParameters,
    IndexCounts,
    IndexManifest,
    ManifestFile,
    metadata_document,
    read_manifest,
    write_manifest,
)
from repo_dive.indexing.vectors import EmbeddingIdentity


def manifest() -> IndexManifest:
    return IndexManifest(
        build_id="build-123",
        repository_fingerprint="fingerprint",
        scan_mode="filesystem",
        parameters=BuildParameters(
            include=("src/**",),
            exclude=("dist/**",),
            max_file_size=1000,
            max_chunk_lines=50,
        ),
        files=(
            ManifestFile(
                path="src/app.py",
                content_hash="hash-app",
                status="read",
                chunk_ids=("chunk:1", "chunk:2"),
            ),
        ),
        counts=IndexCounts(
            files=1,
            indexed_files=1,
            skipped_files=0,
            chunks=2,
            symbols=1,
            relationships=0,
        ),
    )


def test_manifest_round_trip_is_stable_and_metadata_points_to_generation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manifest.json"
    expected = manifest()

    write_manifest(path, expected)

    assert read_manifest(path) == expected
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert metadata_document(expected) == {
        "schema_version": "2.0",
        "index": {
            "build_id": "build-123",
            "database": ".repo-dive/index/index.sqlite3",
            "manifest": ".repo-dive/index/manifest.json",
            "repository_fingerprint": "fingerprint",
        },
    }
    assert expected.parameters.parser_version == "2"
    assert expected.parameters.index_schema_version == 5


def test_manifest_round_trip_records_optional_embedding_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manifest.json"
    configured = manifest()
    expected = IndexManifest(
        build_id=configured.build_id,
        repository_fingerprint=configured.repository_fingerprint,
        scan_mode=configured.scan_mode,
        parameters=configured.parameters,
        files=configured.files,
        counts=configured.counts,
        embedding=EmbeddingIdentity(
            provider="fake",
            model="fixture-v1",
            dimensions=2,
        ),
    )

    write_manifest(path, expected)

    assert read_manifest(path) == expected
    assert expected.to_document()["embedding"] == {
        "dimensions": 2,
        "model": "fixture-v1",
        "provider": "fake",
    }
    assert "embedding" not in manifest().to_document()


def test_manifest_rejects_unknown_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"schema_version":"99.0"}\n', encoding="utf-8")

    with pytest.raises(RepositoryError) as exc_info:
        read_manifest(path)

    assert exc_info.value.code == "index_manifest_version_unsupported"


def test_manifest_rejects_invalid_external_data_without_leaking_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"schema_version":"1.0","build_id":42}\n', encoding="utf-8")

    with pytest.raises(RepositoryError) as exc_info:
        read_manifest(path)

    assert exc_info.value.code == "index_manifest_version_unsupported"
    assert exc_info.value.details == {"actual": "1.0", "expected": "2.0"}


def test_manifest_rejects_malformed_git_commit_identity() -> None:
    with pytest.raises(ValueError, match="full lowercase Git object ID"):
        replace(
            manifest(),
            source_control="git",
            source_commit="ABC123",
            source_dirty=False,
        )
