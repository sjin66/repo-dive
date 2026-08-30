"""Incremental repository indexing with generation-based atomic publication."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import uuid
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from repo_dive.errors import (
    InternalOperationError,
    InvocationError,
    RepoDiveError,
    RepositoryError,
)
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
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION, IndexStore
from repo_dive.indexing.vectors import (
    ChunkVector,
    EmbeddingIdentity,
    create_chunk_vector,
)
from repo_dive.parsing.models import Chunk, ParseDiagnostic, ParseResult
from repo_dive.parsing.pipeline import ParsingPipeline
from repo_dive.providers.embeddings import EmbeddingProvider, VectorFailurePolicy
from repo_dive.scanner.models import Inventory, ReadStatus, SourceFile
from repo_dive.scanner.service import scan_repository
from repo_dive.schema import JsonObject, serialize_json_document
from repo_dive.storage.paths import resolve_repository, resolve_within_repository

INDEX_DIRECTORY = ".repo-dive/index"
GENERATIONS_DIRECTORY = ".repo-dive/index-generations"
DATABASE_NAME = "index.sqlite3"
MANIFEST_NAME = "manifest.json"
METADATA_NAME = "metadata.json"

VectorBuildStatus = Literal["ready", "degraded"]


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
    vector: VectorBuildResult | None = None
    diagnostics: tuple[ParseDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class VectorBuildResult:
    """Observable cost and failure state for one requested vector build."""

    status: VectorBuildStatus
    failure_policy: VectorFailurePolicy
    identity: EmbeddingIdentity
    total_chunks: int
    embedded_chunks: int
    reused_chunks: int
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class PublishedIndex:
    """A validated, current index generation opened by read-only consumers."""

    repository: Path
    manifest: IndexManifest
    database: Path


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
        embedding_provider: EmbeddingProvider | None = None,
        vector_failure: VectorFailurePolicy = "strict",
    ) -> IndexBuildResult:
        """Build or incrementally replace the selected repository index."""
        if vector_failure not in ("strict", "degraded"):
            raise ValueError("vector_failure must be strict or degraded")
        root = resolve_repository(repository)
        parameters = BuildParameters(
            include=tuple(sorted(set(include))),
            exclude=tuple(sorted(set(exclude))),
            max_file_size=max_file_size,
            max_chunk_lines=max_chunk_lines,
        )
        stage = "embedding_setup"
        staging: Path | None = None
        try:
            embedding_identity = (
                embedding_provider.identity if embedding_provider is not None else None
            )
            stage = "scan"
            inventory = scan_repository(
                root,
                include=parameters.include,
                exclude=parameters.exclude,
                max_file_size=parameters.max_file_size,
            )
            current = _load_current_index(root, allow_schema_upgrade=True)
            if (
                current is not None
                and current.manifest.parameters == parameters
                and current.manifest.repository_fingerprint
                == inventory.repository_fingerprint
                and (
                    embedding_provider is None
                    or current.manifest.embedding == embedding_identity
                )
            ):
                return _result_from_manifest(
                    current.manifest,
                    reused_files=current.manifest.counts.files,
                    embedding_identity=embedding_identity,
                    vector_failure=vector_failure,
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
                embedding_provider=embedding_provider,
                embedding_identity=embedding_identity,
                vector_failure=vector_failure,
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
        embedding_provider: EmbeddingProvider | None,
        embedding_identity: EmbeddingIdentity | None,
        vector_failure: VectorFailurePolicy,
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
        vector_result: VectorBuildResult | None = None

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
            if embedding_provider is not None and embedding_identity is not None:
                vector_result = _build_vector_index(
                    store=store,
                    previous_store=previous_store,
                    previous_identity=(
                        current.manifest.embedding if current is not None else None
                    ),
                    chunks=tuple(chunks),
                    provider=embedding_provider,
                    identity=embedding_identity,
                    failure_policy=vector_failure,
                )
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
            embedding=(
                embedding_identity
                if vector_result is not None and vector_result.status == "ready"
                else None
            ),
        )
        return (
            IndexBuildResult(
                build_id=build_id,
                repository_fingerprint=inventory.repository_fingerprint,
                counts=counts,
                reused_files=reused_files,
                rebuilt_files=rebuilt_files,
                deleted_files=deleted_files,
                vector=vector_result,
                diagnostics=tuple(diagnostics),
            ),
            manifest,
        )


def load_published_index(repository: str | Path) -> PublishedIndex:
    """Load a complete current index without creating or replacing artifacts."""
    root = resolve_repository(repository)
    current = _load_current_index(root)
    if current is None:
        raise RepositoryError(
            "index_not_found",
            "Repository index does not exist; run `repo-dive index` first.",
            details={"path": str(root / INDEX_DIRECTORY)},
        )

    parameters = current.manifest.parameters
    inventory = scan_repository(
        root,
        include=parameters.include,
        exclude=parameters.exclude,
        max_file_size=parameters.max_file_size,
    )
    if inventory.repository_fingerprint != current.manifest.repository_fingerprint:
        raise RepositoryError(
            "index_stale",
            "Repository index is stale; run `repo-dive index` first.",
            details={"build_id": current.manifest.build_id},
        )
    return PublishedIndex(
        repository=root,
        manifest=current.manifest,
        database=current.generation / DATABASE_NAME,
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


def _build_vector_index(
    *,
    store: IndexStore,
    previous_store: IndexStore | None,
    previous_identity: EmbeddingIdentity | None,
    chunks: tuple[Chunk, ...],
    provider: EmbeddingProvider,
    identity: EmbeddingIdentity,
    failure_policy: VectorFailurePolicy,
) -> VectorBuildResult:
    try:
        reusable = _reusable_vectors(
            previous_store=previous_store,
            previous_identity=previous_identity,
            identity=identity,
        )
        reused = tuple(
            reusable[chunk.id]
            for chunk in chunks
            if chunk.id in reusable
            and reusable[chunk.id].chunk_hash == chunk.content_hash
        )
        reused_ids = {vector.chunk_id for vector in reused}
        pending = tuple(chunk for chunk in chunks if chunk.id not in reused_ids)
        embeddings = provider.embed(tuple(chunk.text for chunk in pending))
        embedded = tuple(
            create_chunk_vector(chunk, identity, embedding)
            for chunk, embedding in zip(pending, embeddings, strict=True)
        )
        store.replace_vector_index(identity, (*reused, *embedded))
    except Exception as error:
        if failure_policy == "strict":
            raise _GenerationFailure("embedding") from error
        return VectorBuildResult(
            status="degraded",
            failure_policy=failure_policy,
            identity=identity,
            total_chunks=len(chunks),
            embedded_chunks=0,
            reused_chunks=0,
            error_code=_safe_error_code(error),
        )
    return VectorBuildResult(
        status="ready",
        failure_policy=failure_policy,
        identity=identity,
        total_chunks=len(chunks),
        embedded_chunks=len(embedded),
        reused_chunks=len(reused),
    )


def _reusable_vectors(
    *,
    previous_store: IndexStore | None,
    previous_identity: EmbeddingIdentity | None,
    identity: EmbeddingIdentity,
) -> dict[str, ChunkVector]:
    if previous_store is None or previous_identity != identity:
        return {}
    return {
        vector.chunk_id: vector for vector in previous_store.get_vector_index(identity)
    }


def _safe_error_code(error: Exception) -> str:
    return error.code if isinstance(error, RepoDiveError) else "embedding_failed"


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


def _load_current_index(
    root: Path,
    *,
    allow_schema_upgrade: bool = False,
) -> _CurrentIndex | None:
    pointer = root / INDEX_DIRECTORY
    if not os.path.lexists(pointer):
        return None
    if not pointer.is_symlink() and not _is_directory_junction(pointer):
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
    if (
        allow_schema_upgrade
        and manifest.parameters.index_schema_version != INDEX_SCHEMA_VERSION
    ):
        return _CurrentIndex(manifest=manifest, generation=generation)
    try:
        with IndexStore.open_readonly(generation / DATABASE_NAME) as store:
            if store.foreign_key_violations() or store.integrity_check() != ("ok",):
                raise RepositoryError(
                    "index_integrity_error",
                    "Published repository index failed integrity checks.",
                )
    except sqlite3.Error as error:
        raise RepositoryError(
            "index_integrity_error",
            "Published repository index failed integrity checks.",
        ) from error
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
        _create_index_pointer(temporary_pointer, build_id)
        _replace_index_pointer(temporary_pointer, pointer, build_id)
    except (OSError, subprocess.SubprocessError) as error:
        _remove_index_pointer(temporary_pointer)
        if moved:
            _cleanup_directory(generation)
        raise InternalOperationError(
            "index_publish_failed",
            "Could not atomically publish repository index.",
        ) from error


def _create_index_pointer(pointer: Path, build_id: str) -> None:
    target = Path("index-generations") / build_id
    if os.name == "nt":
        # Keep shell-parsed arguments limited to generated path components. Passing
        # absolute repository paths through cmd.exe would allow valid Windows path
        # characters such as `&` to be interpreted as command separators.
        subprocess.run(
            [
                os.environ.get("COMSPEC", "cmd.exe"),
                "/d",
                "/c",
                "mklink",
                "/J",
                pointer.name,
                str(target),
            ],
            check=True,
            capture_output=True,
            cwd=pointer.parent,
        )
        return
    os.symlink(
        target,
        pointer,
        target_is_directory=True,
    )


def _replace_index_pointer(temporary: Path, pointer: Path, build_id: str) -> None:
    if os.name != "nt" or not os.path.lexists(pointer):
        os.replace(temporary, pointer)
        return

    previous = pointer.parent / f".index.{build_id}.previous"
    os.replace(pointer, previous)
    try:
        os.replace(temporary, pointer)
    except OSError:
        os.replace(previous, pointer)
        raise
    _remove_index_pointer(previous)


def _is_directory_junction(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        status = path.lstat()
    except OSError:
        return False
    return bool(
        stat.S_ISDIR(status.st_mode)
        and getattr(status, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        and getattr(status, "st_reparse_tag", None)
        == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", None)
    )


def _remove_index_pointer(pointer: Path) -> None:
    with suppress(OSError):
        if _is_directory_junction(pointer):
            pointer.rmdir()
        else:
            pointer.unlink(missing_ok=True)


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
    embedding_identity: EmbeddingIdentity | None = None,
    vector_failure: VectorFailurePolicy = "strict",
) -> IndexBuildResult:
    vector = (
        VectorBuildResult(
            status="ready",
            failure_policy=vector_failure,
            identity=embedding_identity,
            total_chunks=manifest.counts.chunks,
            embedded_chunks=0,
            reused_chunks=manifest.counts.chunks,
        )
        if embedding_identity is not None and manifest.embedding == embedding_identity
        else None
    )
    return IndexBuildResult(
        build_id=manifest.build_id,
        repository_fingerprint=manifest.repository_fingerprint,
        counts=manifest.counts,
        reused_files=reused_files,
        rebuilt_files=0,
        deleted_files=0,
        vector=vector,
    )


__all__ = [
    "IndexBuildResult",
    "IndexService",
    "PublishedIndex",
    "SourceParser",
    "VectorBuildResult",
    "VectorFailurePolicy",
    "load_published_index",
]
