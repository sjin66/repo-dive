"""Incremental repository indexing with generation-based atomic publication."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from repo_dive.errors import InternalOperationError, InvocationError, RepositoryError
from repo_dive.indexing.bm25 import BM25Parameters, build_bm25_index
from repo_dive.indexing.manifest import (
    BuildParameters,
    IndexCounts,
    IndexManifest,
    ManifestFile,
    metadata_document,
    read_manifest,
    write_manifest,
)
from repo_dive.indexing.store import IndexStore
from repo_dive.parsing.models import Chunk, ParseDiagnostic, ParseResult
from repo_dive.parsing.pipeline import ParsingPipeline
from repo_dive.scanner.models import Inventory, ReadStatus, SourceFile
from repo_dive.scanner.service import scan_repository
from repo_dive.schema import JsonObject, serialize_json_document
from repo_dive.storage.paths import resolve_repository, resolve_within_repository

INDEX_DIRECTORY = ".repo-dive/index"
GENERATIONS_DIRECTORY = ".repo-dive/index-generations"
DATABASE_NAME = "index.sqlite3"
MANIFEST_NAME = "manifest.json"
METADATA_NAME = "metadata.json"


class SourceParser(Protocol):
    """Minimal parser boundary used for indexing and deterministic tests."""

    def parse(self, source: SourceFile) -> ParseResult: ...


@dataclass(frozen=True, slots=True)
class IndexBuildResult:
    """Stable summary of a complete current index generation."""

    build_id: str
    repository_fingerprint: str
    counts: IndexCounts
    reused_files: int
    rebuilt_files: int
    deleted_files: int
    diagnostics: tuple[ParseDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class _CurrentIndex:
    manifest: IndexManifest
    generation: Path


class IndexService:
    """Scan, parse, index, validate, and atomically publish one repository."""

    def build(
        self,
        repository: str | Path,
        *,
        include: tuple[str, ...] = (),
        exclude: tuple[str, ...] = (),
        max_file_size: int = 1_000_000,
        max_chunk_lines: int = 200,
        parser: SourceParser | None = None,
    ) -> IndexBuildResult:
        """Build or incrementally replace the selected repository index."""
        root = resolve_repository(repository)
        parameters = BuildParameters(
            include=tuple(sorted(set(include))),
            exclude=tuple(sorted(set(exclude))),
            max_file_size=max_file_size,
            max_chunk_lines=max_chunk_lines,
        )
        stage = "scan"
        staging: Path | None = None
        try:
            inventory = scan_repository(
                root,
                include=parameters.include,
                exclude=parameters.exclude,
                max_file_size=parameters.max_file_size,
            )
            current = _load_current_index(root)
            if (
                current is not None
                and current.manifest.parameters == parameters
                and current.manifest.repository_fingerprint
                == inventory.repository_fingerprint
            ):
                return _result_from_manifest(
                    current.manifest,
                    reused_files=current.manifest.counts.files,
                )

            stage = "prepare"
            generations = _prepare_generations_directory(root)
            staging = Path(tempfile.mkdtemp(prefix=".build-", dir=generations))
            active_parser = parser or ParsingPipeline(
                max_chunk_lines=parameters.max_chunk_lines
            )
            result, manifest = self._build_generation(
                staging=staging,
                inventory=inventory,
                parameters=parameters,
                current=current,
                parser=active_parser,
            )

            stage = "manifest"
            write_manifest(staging / MANIFEST_NAME, manifest)
            _write_json(staging / METADATA_NAME, metadata_document(manifest))
            if read_manifest(staging / MANIFEST_NAME) != manifest:
                raise InternalOperationError(
                    "index_manifest_invalid",
                    "Generated repository index Manifest did not validate.",
                )

            stage = "publish"
            _publish_generation(
                root=root,
                staging=staging,
                build_id=manifest.build_id,
            )
            staging = None
            return result
        except (InvocationError, RepositoryError):
            if staging is not None:
                _cleanup_directory(staging)
            raise
        except Exception as error:
            cleanup_failed = staging is not None and not _cleanup_directory(staging)
            details: JsonObject = {"stage": stage}
            if cleanup_failed:
                details["temporary_cleanup_failed"] = True
            if isinstance(error, _GenerationFailure):
                details["stage"] = error.stage
                if error.path is not None:
                    details["path"] = error.path
            raise InternalOperationError(
                "index_build_failed",
                "Could not build repository index.",
                details=details,
            ) from error

    def _build_generation(
        self,
        *,
        staging: Path,
        inventory: Inventory,
        parameters: BuildParameters,
        current: _CurrentIndex | None,
        parser: SourceParser,
    ) -> tuple[IndexBuildResult, IndexManifest]:
        compatible = current is not None and current.manifest.parameters == parameters
        previous_paths = (
            {item.path for item in current.manifest.files}
            if compatible and current is not None
            else set()
        )
        current_paths = {source.record.path for source in inventory.files}
        deleted_files = len(previous_paths - current_paths)
        reused_files = 0
        rebuilt_files = 0
        diagnostics: list[ParseDiagnostic] = []
        manifest_files: list[ManifestFile] = []
        chunks: list[Chunk] = []
        symbol_count = 0
        relationship_count = 0

        with ExitStack() as stack:
            store = stack.enter_context(IndexStore.initialize(staging / DATABASE_NAME))
            previous_store = (
                stack.enter_context(IndexStore.open(current.generation / DATABASE_NAME))
                if compatible and current is not None
                else None
            )
            for source in inventory.files:
                try:
                    parsed, reused = _parse_or_reuse(
                        source=source,
                        parser=parser,
                        previous_store=previous_store,
                    )
                except Exception as error:
                    raise _GenerationFailure(
                        "parse",
                        path=source.record.path,
                    ) from error
                reused_files += int(reused)
                rebuilt_files += int(not reused)
                try:
                    store.replace_document(source, parsed)
                except Exception as error:
                    raise _GenerationFailure(
                        "write",
                        path=source.record.path,
                    ) from error
                chunks.extend(parsed.chunks)
                symbol_count += len(parsed.symbols)
                relationship_count += len(parsed.relationships)
                diagnostics.extend(parsed.diagnostics)
                manifest_files.append(
                    ManifestFile(
                        path=source.record.path,
                        content_hash=source.record.content_hash,
                        status=source.record.status.value,
                        chunk_ids=tuple(chunk.id for chunk in parsed.chunks),
                    )
                )

            try:
                store.replace_bm25_index(
                    build_bm25_index(
                        chunks,
                        parameters=BM25Parameters(
                            k1=parameters.bm25_k1,
                            b=parameters.bm25_b,
                            tokenizer_version=parameters.tokenizer_version,
                        ),
                    )
                )
            except Exception as error:
                raise _GenerationFailure("bm25") from error
            if store.foreign_key_violations() or store.integrity_check() != ("ok",):
                raise _GenerationFailure("validate")

        counts = IndexCounts(
            files=len(inventory.files),
            indexed_files=sum(
                source.record.status is ReadStatus.READ for source in inventory.files
            ),
            skipped_files=sum(
                source.record.status is ReadStatus.SKIPPED for source in inventory.files
            ),
            chunks=len(chunks),
            symbols=symbol_count,
            relationships=relationship_count,
        )
        build_id = uuid.uuid4().hex
        manifest = IndexManifest(
            build_id=build_id,
            repository_fingerprint=inventory.repository_fingerprint,
            scan_mode=inventory.mode,
            parameters=parameters,
            files=tuple(manifest_files),
            counts=counts,
        )
        return (
            IndexBuildResult(
                build_id=build_id,
                repository_fingerprint=inventory.repository_fingerprint,
                counts=counts,
                reused_files=reused_files,
                rebuilt_files=rebuilt_files,
                deleted_files=deleted_files,
                diagnostics=tuple(diagnostics),
            ),
            manifest,
        )


class _GenerationFailure(Exception):
    def __init__(self, stage: str, *, path: str | None = None) -> None:
        super().__init__(stage)
        self.stage = stage
        self.path = path


def _parse_or_reuse(
    *,
    source: SourceFile,
    parser: SourceParser,
    previous_store: IndexStore | None,
) -> tuple[ParseResult, bool]:
    if previous_store is not None:
        previous_record = previous_store.get_file(source.record.path)
        if previous_record == source.record:
            return previous_store.get_parse_result(source.record.path), True
    return parser.parse(source), False


def _prepare_generations_directory(root: Path) -> Path:
    generations = resolve_within_repository(root, GENERATIONS_DIRECTORY)
    try:
        generations.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise InternalOperationError(
            "index_directory_unavailable",
            "Could not prepare repository index directory.",
        ) from error
    return resolve_within_repository(root, GENERATIONS_DIRECTORY, must_exist=True)


def _load_current_index(root: Path) -> _CurrentIndex | None:
    pointer = root / INDEX_DIRECTORY
    if not os.path.lexists(pointer):
        return None
    if not pointer.is_symlink():
        raise RepositoryError(
            "index_pointer_invalid",
            "Repository index pointer is invalid.",
        )
    try:
        generation = pointer.resolve(strict=True)
    except OSError as error:
        raise RepositoryError(
            "index_pointer_invalid",
            "Repository index pointer is invalid.",
        ) from error
    generations = resolve_within_repository(
        root,
        GENERATIONS_DIRECTORY,
        must_exist=True,
    )
    if generation.parent != generations:
        raise RepositoryError(
            "index_pointer_invalid",
            "Repository index pointer is invalid.",
        )
    manifest = read_manifest(generation / MANIFEST_NAME)
    _validate_metadata(generation / METADATA_NAME, manifest)
    with IndexStore.open(generation / DATABASE_NAME) as store:
        if store.foreign_key_violations() or store.integrity_check() != ("ok",):
            raise RepositoryError(
                "index_integrity_error",
                "Published repository index failed integrity checks.",
            )
    return _CurrentIndex(manifest=manifest, generation=generation)


def _validate_metadata(path: Path, manifest: IndexManifest) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RepositoryError(
            "index_metadata_invalid",
            "Repository index metadata is invalid.",
        ) from error
    if document != metadata_document(manifest):
        raise RepositoryError(
            "index_metadata_invalid",
            "Repository index metadata is invalid.",
        )


def _write_json(path: Path, document: JsonObject) -> None:
    try:
        path.write_text(serialize_json_document(document), encoding="utf-8")
    except OSError as error:
        raise InternalOperationError(
            "index_metadata_write_failed",
            "Could not write repository index metadata.",
        ) from error


def _publish_generation(*, root: Path, staging: Path, build_id: str) -> None:
    generations = resolve_within_repository(
        root,
        GENERATIONS_DIRECTORY,
        must_exist=True,
    )
    generation = generations / build_id
    pointer = root / INDEX_DIRECTORY
    temporary_pointer = pointer.parent / f".index.{build_id}.tmp"
    moved = False
    try:
        os.replace(staging, generation)
        moved = True
        os.symlink(
            Path("index-generations") / build_id,
            temporary_pointer,
            target_is_directory=True,
        )
        os.replace(temporary_pointer, pointer)
    except OSError as error:
        with suppress(OSError):
            temporary_pointer.unlink(missing_ok=True)
        if moved:
            _cleanup_directory(generation)
        raise InternalOperationError(
            "index_publish_failed",
            "Could not atomically publish repository index.",
        ) from error


def _cleanup_directory(path: Path) -> bool:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def _result_from_manifest(
    manifest: IndexManifest,
    *,
    reused_files: int,
) -> IndexBuildResult:
    return IndexBuildResult(
        build_id=manifest.build_id,
        repository_fingerprint=manifest.repository_fingerprint,
        counts=manifest.counts,
        reused_files=reused_files,
        rebuilt_files=0,
        deleted_files=0,
    )


__all__ = ["IndexBuildResult", "IndexService", "SourceParser"]
