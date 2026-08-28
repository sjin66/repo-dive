"""Public `repo-dive index` command boundary."""

from __future__ import annotations

import argparse

from repo_dive.commands import Command, CommandOutput, OutputFormat
from repo_dive.indexing.manifest import INDEX_MANIFEST_VERSION
from repo_dive.indexing.service import IndexBuildResult, IndexService
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION
from repo_dive.parsing.models import ParseDiagnostic
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
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="result output format (default: json)",
    )


def handle(args: argparse.Namespace) -> CommandOutput:
    """Build the selected repository index and format its stable summary."""
    root = resolve_repository(args.repository)
    result = IndexService().build(
        root,
        include=tuple(args.include),
        exclude=tuple(args.exclude),
        max_file_size=args.max_file_size,
        max_chunk_lines=args.max_chunk_lines,
    )
    output_format: OutputFormat = args.format
    warnings = tuple(_diagnostic_warning(item) for item in result.diagnostics)
    output = (
        _markdown_summary(result, warnings=warnings)
        if output_format == "markdown"
        else _json_result(result, warning_count=len(warnings))
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


def _json_result(result: IndexBuildResult, *, warning_count: int) -> JsonObject:
    counts = result.counts
    return {
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


def _markdown_summary(
    result: IndexBuildResult,
    *,
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
