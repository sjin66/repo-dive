"""Versioned public metadata for a published repository index generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.indexing.bm25 import DEFAULT_B, DEFAULT_K1, TOKENIZER_VERSION
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION
from repo_dive.schema import JsonObject, JsonValue, serialize_json_document

INDEX_MANIFEST_VERSION = "1.0"
PARSER_VERSION = "1"

ManifestStatus = Literal["read", "skipped"]
ManifestScanMode = Literal["git", "filesystem"]


@dataclass(frozen=True, slots=True)
class BuildParameters:
    """Every setting that can change the deterministic index output."""

    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    max_file_size: int = 1_000_000
    max_chunk_lines: int = 200
    parser_version: str = PARSER_VERSION
    tokenizer_version: str = TOKENIZER_VERSION
    index_schema_version: int = INDEX_SCHEMA_VERSION
    bm25_k1: float = DEFAULT_K1
    bm25_b: float = DEFAULT_B

    def __post_init__(self) -> None:
        if self.max_file_size <= 0 or self.max_chunk_lines <= 0:
            raise ValueError("index build limits must be positive")
        if not self.parser_version or not self.tokenizer_version:
            raise ValueError("index component versions must not be empty")
        if self.index_schema_version <= 0 or self.bm25_k1 <= 0:
            raise ValueError("index schema version and BM25 k1 must be positive")
        if not 0 <= self.bm25_b <= 1:
            raise ValueError("BM25 b must be between 0 and 1")

    def to_document(self) -> JsonObject:
        return {
            "bm25_b": self.bm25_b,
            "bm25_k1": self.bm25_k1,
            "exclude": list(self.exclude),
            "include": list(self.include),
            "index_schema_version": self.index_schema_version,
            "max_chunk_lines": self.max_chunk_lines,
            "max_file_size": self.max_file_size,
            "parser_version": self.parser_version,
            "tokenizer_version": self.tokenizer_version,
        }


@dataclass(frozen=True, slots=True)
class ManifestFile:
    """Published identity and Chunk membership for one repository file."""

    path: str
    content_hash: str | None
    status: ManifestStatus
    chunk_ids: tuple[str, ...] = ()

    def to_document(self) -> JsonObject:
        return {
            "chunk_ids": list(self.chunk_ids),
            "content_hash": self.content_hash,
            "path": self.path,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class IndexCounts:
    """Stable aggregate counts for one complete generation."""

    files: int
    indexed_files: int
    skipped_files: int
    chunks: int
    symbols: int
    relationships: int

    def __post_init__(self) -> None:
        if any(value < 0 for value in self.values()):
            raise ValueError("index counts must not be negative")
        if self.indexed_files + self.skipped_files != self.files:
            raise ValueError("indexed and skipped files must equal total files")

    def values(self) -> tuple[int, ...]:
        return (
            self.files,
            self.indexed_files,
            self.skipped_files,
            self.chunks,
            self.symbols,
            self.relationships,
        )

    def to_document(self) -> JsonObject:
        return {
            "chunks": self.chunks,
            "files": self.files,
            "indexed_files": self.indexed_files,
            "relationships": self.relationships,
            "skipped_files": self.skipped_files,
            "symbols": self.symbols,
        }


@dataclass(frozen=True, slots=True)
class IndexManifest:
    """Complete, versioned description of one published index generation."""

    build_id: str
    repository_fingerprint: str
    scan_mode: ManifestScanMode
    parameters: BuildParameters
    files: tuple[ManifestFile, ...]
    counts: IndexCounts
    schema_version: str = INDEX_MANIFEST_VERSION

    def __post_init__(self) -> None:
        if not self.build_id or not self.repository_fingerprint:
            raise ValueError("manifest identities must not be empty")
        if self.schema_version != INDEX_MANIFEST_VERSION:
            raise ValueError("manifest schema version is not supported")
        paths = tuple(item.path for item in self.files)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("manifest files must have unique sorted paths")
        if self.counts.files != len(self.files):
            raise ValueError("manifest file count does not match files")

    def to_document(self) -> JsonObject:
        return {
            "build_id": self.build_id,
            "counts": self.counts.to_document(),
            "files": [item.to_document() for item in self.files],
            "parameters": self.parameters.to_document(),
            "repository_fingerprint": self.repository_fingerprint,
            "scan_mode": self.scan_mode,
            "schema_version": self.schema_version,
        }


def write_manifest(path: Path, manifest: IndexManifest) -> None:
    """Write a complete Manifest inside an unpublished generation directory."""
    try:
        path.write_text(
            serialize_json_document(manifest.to_document()),
            encoding="utf-8",
        )
    except OSError as error:
        raise InternalOperationError(
            "index_manifest_write_failed",
            "Could not write repository index Manifest.",
        ) from error


def read_manifest(path: Path) -> IndexManifest:
    """Read and strictly validate an untrusted persisted Manifest."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RepositoryError(
            "index_manifest_invalid",
            "Repository index Manifest is invalid.",
        ) from error

    if isinstance(document, dict):
        version = document.get("schema_version")
        if isinstance(version, str) and version != INDEX_MANIFEST_VERSION:
            raise RepositoryError(
                "index_manifest_version_unsupported",
                "Repository index Manifest version is not supported.",
                details={"actual": version, "expected": INDEX_MANIFEST_VERSION},
            )
    try:
        return _manifest_from_document(_object(document))
    except (KeyError, TypeError, ValueError) as error:
        raise RepositoryError(
            "index_manifest_invalid",
            "Repository index Manifest is invalid.",
        ) from error


def metadata_document(manifest: IndexManifest) -> JsonObject:
    """Return the stable public pointer metadata for the current generation."""
    index: JsonObject = {
        "build_id": manifest.build_id,
        "database": ".repo-dive/index/index.sqlite3",
        "manifest": ".repo-dive/index/manifest.json",
        "repository_fingerprint": manifest.repository_fingerprint,
    }
    return {"schema_version": INDEX_MANIFEST_VERSION, "index": index}


def _manifest_from_document(document: JsonObject) -> IndexManifest:
    parameters = _object(document["parameters"])
    counts = _object(document["counts"])
    return IndexManifest(
        build_id=_string(document["build_id"]),
        repository_fingerprint=_string(document["repository_fingerprint"]),
        scan_mode=cast(
            ManifestScanMode, _enum(document["scan_mode"], {"git", "filesystem"})
        ),
        parameters=BuildParameters(
            include=_string_tuple(parameters["include"]),
            exclude=_string_tuple(parameters["exclude"]),
            max_file_size=_integer(parameters["max_file_size"]),
            max_chunk_lines=_integer(parameters["max_chunk_lines"]),
            parser_version=_string(parameters["parser_version"]),
            tokenizer_version=_string(parameters["tokenizer_version"]),
            index_schema_version=_integer(parameters["index_schema_version"]),
            bm25_k1=_number(parameters["bm25_k1"]),
            bm25_b=_number(parameters["bm25_b"]),
        ),
        files=tuple(
            _manifest_file_from_document(_object(item))
            for item in _array(document["files"])
        ),
        counts=IndexCounts(
            files=_integer(counts["files"]),
            indexed_files=_integer(counts["indexed_files"]),
            skipped_files=_integer(counts["skipped_files"]),
            chunks=_integer(counts["chunks"]),
            symbols=_integer(counts["symbols"]),
            relationships=_integer(counts["relationships"]),
        ),
        schema_version=_string(document["schema_version"]),
    )


def _manifest_file_from_document(document: JsonObject) -> ManifestFile:
    content_hash_value = document["content_hash"]
    if content_hash_value is not None and not isinstance(content_hash_value, str):
        raise TypeError("content_hash must be a string or null")
    return ManifestFile(
        path=_string(document["path"]),
        content_hash=content_hash_value,
        status=cast(ManifestStatus, _enum(document["status"], {"read", "skipped"})),
        chunk_ids=_string_tuple(document["chunk_ids"]),
    )


def _object(value: object) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("value must be an object")
    return cast(JsonObject, value)


def _array(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError("value must be an array")
    return value


def _string(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    return value


def _string_tuple(value: JsonValue) -> tuple[str, ...]:
    values = _array(value)
    if not all(isinstance(item, str) for item in values):
        raise TypeError("value must contain only strings")
    return tuple(cast(list[str], values))


def _integer(value: JsonValue) -> int:
    if type(value) is not int:
        raise TypeError("value must be an integer")
    return value


def _number(value: JsonValue) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("value must be a number")
    return float(value)


def _enum(value: JsonValue, allowed: set[str]) -> str:
    text = _string(value)
    if text not in allowed:
        raise ValueError("enum value is invalid")
    return text


__all__ = [
    "BuildParameters",
    "INDEX_MANIFEST_VERSION",
    "IndexCounts",
    "IndexManifest",
    "ManifestFile",
    "metadata_document",
    "read_manifest",
    "write_manifest",
]
