"""Public `repo-dive index` command boundary."""

from __future__ import annotations

import argparse

from repo_dive.commands import Command, CommandOutput, OutputFormat
from repo_dive.commands.retrieval_arguments import (
    add_embedding_arguments,
    vector_failure_policy,
)
from repo_dive.indexing.manifest import INDEX_MANIFEST_VERSION
from repo_dive.indexing.service import IndexBuildResult, IndexService, VectorBuildResult
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION
from repo_dive.indexing.vectors import EmbeddingIdentity
from repo_dive.parsing.models import ParseDiagnostic
from repo_dive.providers.selection import (
    EmbeddingSelection,
    select_local_embedding_provider,
)
from repo_dive.scanner.service import DEFAULT_MAX_FILE_SIZE
from repo_dive.schema import JsonObject
from repo_dive.storage.paths import resolve_repository

DEFAULT_MAX_CHUNK_LINES = 200


def configure(parser: argparse.ArgumentParser) -> None:
    """Configure bounded, non-interactive index arguments."""
    parser.add_argument("repository", help="local repository directory")
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help="include matching repository paths; repeatable",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="exclude matching repository paths; repeatable",
    )
    parser.add_argument(
        "--max-file-size",
        type=_positive_integer,
        default=DEFAULT_MAX_FILE_SIZE,
        metavar="BYTES",
        help="maximum bytes read from one file",
    )
    parser.add_argument(
        "--max-chunk-lines",
        type=_positive_integer,
        default=DEFAULT_MAX_CHUNK_LINES,
        metavar="LINES",
        help="maximum source lines in one Chunk",
    )
    add_embedding_arguments(parser)
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="result output format (default: json)",
    )


def handle(args: argparse.Namespace) -> CommandOutput:
    """Build the selected repository index and format its stable summary."""
    root = resolve_repository(args.repository)
    selection = select_local_embedding_provider(
        args.embedding_model,
        failure_policy=vector_failure_policy(args.vector_failure),
    )
    result = IndexService().build(
        root,
        include=tuple(args.include),
        exclude=tuple(args.exclude),
        max_file_size=args.max_file_size,
        max_chunk_lines=args.max_chunk_lines,
        embedding_provider=selection.provider,
        vector_failure=selection.failure_policy,
    )
    output_format: OutputFormat = args.format
    warnings = tuple(_diagnostic_warning(item) for item in result.diagnostics) + tuple(
        warning
        for warning in (selection.warning, _vector_warning(result.vector))
        if warning is not None
    )
    output = (
        _markdown_summary(result, selection=selection, warnings=warnings)
        if output_format == "markdown"
        else _json_result(
            result,
            selection=selection,
            warning_count=len(warnings),
        )
    )
    return CommandOutput(
        command="index",
        format=output_format,
        result=output,
        repository=str(root),
        warnings=warnings,
    )


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _diagnostic_warning(diagnostic: ParseDiagnostic) -> str:
    location = (
        f"{diagnostic.path}:{diagnostic.line}"
        if diagnostic.line is not None
        else diagnostic.path
    )
    return f"{diagnostic.code}:{location}"


def _json_result(
    result: IndexBuildResult,
    *,
    selection: EmbeddingSelection,
    warning_count: int,
) -> JsonObject:
    counts = result.counts
    document: JsonObject = {
        "build_id": result.build_id,
        "chunks": counts.chunks,
        "deleted_files": result.deleted_files,
        "files": counts.files,
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "indexed_files": counts.indexed_files,
        "manifest_schema_version": INDEX_MANIFEST_VERSION,
        "rebuilt_files": result.rebuilt_files,
        "relationships": counts.relationships,
        "repository_fingerprint": result.repository_fingerprint,
        "reused_files": result.reused_files,
        "skipped_files": counts.skipped_files,
        "symbols": counts.symbols,
        "warning_count": warning_count,
    }
    if selection.requested:
        document["vector"] = _json_vector(result, selection=selection)
    return document


def _json_vector(
    result: IndexBuildResult,
    *,
    selection: EmbeddingSelection,
) -> JsonObject:
    vector = result.vector
    return {
        "embedded_chunks": vector.embedded_chunks if vector is not None else 0,
        "error_code": (
            vector.error_code if vector is not None else selection.error_code
        ),
        "failure_policy": selection.failure_policy,
        "identity": _json_identity(
            vector.identity if vector is not None else selection.identity
        ),
        "reused_chunks": vector.reused_chunks if vector is not None else 0,
        "status": vector.status if vector is not None else "degraded",
        "total_chunks": vector.total_chunks
        if vector is not None
        else result.counts.chunks,
    }


def _json_identity(identity: EmbeddingIdentity | None) -> JsonObject | None:
    if identity is None:
        return None
    return {
        "dimensions": identity.dimensions,
        "model": identity.model,
        "provider": identity.provider,
    }


def _vector_warning(vector: VectorBuildResult | None) -> str | None:
    if vector is None or vector.error_code is None:
        return None
    return f"vector_degraded:{vector.error_code}"


def _markdown_summary(
    result: IndexBuildResult,
    *,
    selection: EmbeddingSelection,
    warnings: tuple[str, ...],
) -> str:
    counts = result.counts
    lines = [
        "# Repository index",
        "",
        f"- Build ID: `{result.build_id}`",
        f"- Files: {counts.files}",
        f"- Indexed files: {counts.indexed_files}",
        f"- Skipped files: {counts.skipped_files}",
        f"- Chunks: {counts.chunks}",
        f"- Symbols: {counts.symbols}",
        f"- Relationships: {counts.relationships}",
        f"- Reused files: {result.reused_files}",
        f"- Rebuilt files: {result.rebuilt_files}",
        f"- Deleted files: {result.deleted_files}",
        f"- Warnings: {len(warnings)}",
        f"- Index Schema: {INDEX_SCHEMA_VERSION}",
        f"- Manifest Schema: {INDEX_MANIFEST_VERSION}",
    ]
    if selection.requested:
        vector = _json_vector(result, selection=selection)
        lines.extend(
            (
                f"- Vector status: {vector['status']}",
                f"- Vector failure policy: {vector['failure_policy']}",
                f"- Embedded Chunks: {vector['embedded_chunks']}",
                f"- Reused vectors: {vector['reused_chunks']}",
            )
        )
    if warnings:
        lines.extend(("", "## Warnings", ""))
        lines.extend(f"- `{warning}`" for warning in warnings)
    return "\n".join(lines) + "\n"


INDEX_COMMAND = Command(
    name="index",
    help="build or incrementally update a local repository index",
    configure=configure,
    handler=handle,
)

__all__ = ["INDEX_COMMAND"]
