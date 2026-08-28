"""Public resumable `repo-dive wiki` command boundaries."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import cast

from repo_dive.commands import Command, CommandOutput, OutputFormat
from repo_dive.commands.context import (
    context_result_document,
    context_result_markdown,
)
from repo_dive.commands.retrieval_arguments import (
    positive_token_budget,
    result_limit,
)
from repo_dive.errors import InvocationError
from repo_dive.parsing.models import Symbol
from repo_dive.retrieval.service import DEFAULT_MAX_RESULTS
from repo_dive.schema import JsonObject, JsonValue
from repo_dive.wiki.models import PageStatus
from repo_dive.wiki.service import (
    STRUCTURE_SCHEMA_VERSION,
    StructureUpdate,
    WikiEvidenceUpdate,
    WikiService,
    WikiState,
    structure_from_document,
)

MAX_STRUCTURE_INPUT_BYTES = 1_000_000


def configure(parser: argparse.ArgumentParser) -> None:
    """Configure explicit non-interactive Wiki subcommands."""
    subparsers = parser.add_subparsers(dest="wiki_command", required=True)

    structure_parser = subparsers.add_parser(
        "structure",
        help="validate and persist an ordered Wiki structure",
    )
    structure_parser.add_argument("repository", help="local repository directory")
    structure_parser.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="UTF-8 JSON structure input file",
    )
    _add_format(structure_parser)
    structure_parser.set_defaults(_wiki_handler=_handle_structure)

    evidence_parser = subparsers.add_parser(
        "evidence",
        help="retrieve and persist grounded Evidence for one Wiki page",
    )
    evidence_parser.add_argument("repository", help="local repository directory")
    evidence_parser.add_argument(
        "--page",
        required=True,
        type=_page_id,
        metavar="PAGE_ID",
        help="stable Page ID from the persisted Wiki structure",
    )
    evidence_parser.add_argument(
        "--token-budget",
        required=True,
        type=positive_token_budget,
        metavar="TOKENS",
        help="positive estimated-token budget for complete page Evidence",
    )
    evidence_parser.add_argument(
        "--max-results",
        type=result_limit,
        default=DEFAULT_MAX_RESULTS,
        metavar="COUNT",
        help="maximum retrieval candidates before budget packing",
    )
    _add_format(evidence_parser)
    evidence_parser.set_defaults(_wiki_handler=_handle_evidence)

    status_parser = subparsers.add_parser(
        "status",
        help="report resumable Wiki page states and next actions",
    )
    status_parser.add_argument("repository", help="local repository directory")
    _add_format(status_parser)
    status_parser.set_defaults(_wiki_handler=_handle_status)


def handle(args: argparse.Namespace) -> CommandOutput:
    """Dispatch one already validated Wiki subcommand."""
    handler = getattr(args, "_wiki_handler", None)
    if handler is None:
        raise InvocationError("invalid_invocation", "A Wiki subcommand is required.")
    return cast(CommandOutput, handler(args))


def _add_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="result output format (default: json)",
    )


def _handle_structure(args: argparse.Namespace) -> CommandOutput:
    document = _read_structure_document(args.input)
    try:
        structure = structure_from_document(document)
    except (KeyError, TypeError, ValueError) as error:
        raise InvocationError(
            "wiki_structure_invalid",
            "Wiki structure input does not match the required Schema.",
        ) from error
    update = WikiService(args.repository).apply_structure(structure)
    output_format: OutputFormat = args.format
    output = (
        _markdown_structure(update)
        if output_format == "markdown"
        else _json_structure(update)
    )
    return CommandOutput(
        command="wiki structure",
        format=output_format,
        result=output,
        repository=str(update.metadata.repository),
    )


def _handle_status(args: argparse.Namespace) -> CommandOutput:
    state = WikiService(args.repository).read_state()
    output_format: OutputFormat = args.format
    output = (
        _markdown_status(state) if output_format == "markdown" else _json_status(state)
    )
    return CommandOutput(
        command="wiki status",
        format=output_format,
        result=output,
        repository=str(state.metadata.repository),
    )


def _handle_evidence(args: argparse.Namespace) -> CommandOutput:
    update = WikiService(args.repository).collect_evidence(
        args.page,
        token_budget=args.token_budget,
        max_results=args.max_results,
    )
    output_format: OutputFormat = args.format
    output = (
        _markdown_evidence(update)
        if output_format == "markdown"
        else _json_evidence(update)
    )
    return CommandOutput(
        command="wiki evidence",
        format=output_format,
        result=output,
        repository=update.metadata.repository,
    )


def _page_id(value: str) -> str:
    if not value or value.strip() != value:
        raise argparse.ArgumentTypeError("Page ID must not be empty or padded")
    return value


def _read_structure_document(input_path: str) -> JsonObject:
    path = Path(input_path)
    try:
        if path.stat().st_size > MAX_STRUCTURE_INPUT_BYTES:
            raise InvocationError(
                "wiki_structure_input_too_large",
                "Wiki structure input exceeds the supported size.",
                details={"max_bytes": MAX_STRUCTURE_INPUT_BYTES},
            )
        value = json.loads(path.read_text(encoding="utf-8"))
    except InvocationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InvocationError(
            "wiki_structure_input_invalid",
            "Wiki structure input is unavailable or invalid JSON.",
        ) from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise InvocationError(
            "wiki_structure_input_invalid",
            "Wiki structure input must be a JSON object.",
        )
    document = cast(JsonObject, value)
    actual_version = document.get("schema_version")
    if isinstance(actual_version, str) and actual_version != STRUCTURE_SCHEMA_VERSION:
        raise InvocationError(
            "wiki_structure_version_unsupported",
            "Wiki structure input version is not supported.",
            details={
                "actual": actual_version,
                "expected": STRUCTURE_SCHEMA_VERSION,
            },
        )
    return document


def _json_structure(update: StructureUpdate) -> JsonObject:
    page_count = sum(len(section.pages) for section in update.wiki.sections)
    return {
        "changed": update.changed,
        "created_page_ids": list(update.created_page_ids),
        "index_build_id": update.metadata.index_build_id,
        "index_schema_version": update.metadata.index_schema_version,
        "invalidated_page_ids": list(update.invalidated_page_ids),
        "metadata_schema_version": update.metadata.schema_version,
        "page_count": page_count,
        "preserved_page_ids": list(update.preserved_page_ids),
        "section_count": len(update.wiki.sections),
        "wiki_schema_version": update.wiki.schema_version,
    }


def _json_status(state: WikiState) -> JsonObject:
    counts = Counter(
        page.status for section in state.wiki.sections for page in section.pages
    )
    page_count = sum(counts.values())
    return {
        "complete": page_count > 0 and counts[PageStatus.GENERATED] == page_count,
        "counts": {status.value: counts[status] for status in PageStatus},
        "description": state.wiki.description,
        "index_build_id": state.metadata.index_build_id,
        "index_schema_version": state.metadata.index_schema_version,
        "metadata_schema_version": state.metadata.schema_version,
        "output_language": state.metadata.output_language,
        "page_count": page_count,
        "repository_fingerprint": state.metadata.repository_fingerprint,
        "sections": [
            {
                "id": section.id,
                "pages": [
                    {
                        "evidence_count": len(page.evidence),
                        "has_body": page.body is not None,
                        "has_error": page.error is not None,
                        "id": page.id,
                        "next_action": _next_action(page.status),
                        "status": page.status.value,
                        "title": page.title,
                    }
                    for page in section.pages
                ],
                "title": section.title,
            }
            for section in state.wiki.sections
        ],
        "title": state.wiki.title,
        "wiki_schema_version": state.wiki.schema_version,
    }


def _json_evidence(update: WikiEvidenceUpdate) -> JsonObject:
    symbols = {symbol.id: symbol for symbol in update.symbols}
    snapshot = update.page.evidence_snapshot
    if snapshot is None:  # pragma: no cover - service postcondition
        raise RuntimeError("Evidence update is missing its persisted snapshot")
    context = context_result_document(
        update.bundle,
        fusion=update.fusion,
        max_results=snapshot.retrieval.max_results,
        symbols=symbols,
    )
    context_items = cast(list[JsonObject], context["items"])
    items: list[JsonValue] = []
    for document, item in zip(context_items, update.bundle.items, strict=True):
        item_document = dict(document)
        item_document["content_hash"] = item.hit.chunk.content_hash
        items.append(item_document)
    return {
        "estimated_tokens": context["estimated_tokens"],
        "estimator": context["estimator"],
        "excluded": context["excluded"],
        "fusion": context["fusion"],
        "generated_at": snapshot.generated_at,
        "index_build_id": snapshot.index_build_id,
        "index_schema_version": snapshot.index_schema_version,
        "items": items,
        "max_results": context["max_results"],
        "page_id": update.page.id,
        "query": context["query"],
        "repository_fingerprint": snapshot.repository_fingerprint,
        "reserved_tokens": context["reserved_tokens"],
        "result_count": context["result_count"],
        "status": update.page.status.value,
        "token_budget": context["token_budget"],
        "truncated": context["truncated"],
    }


def _markdown_structure(update: StructureUpdate) -> str:
    page_count = sum(len(section.pages) for section in update.wiki.sections)
    lines = [
        "# Wiki structure",
        "",
        f"- Changed: {str(update.changed).lower()}",
        f"- Sections: {len(update.wiki.sections)}",
        f"- Pages: {page_count}",
        f"- Created pages: {len(update.created_page_ids)}",
        f"- Invalidated pages: {len(update.invalidated_page_ids)}",
        f"- Preserved pages: {len(update.preserved_page_ids)}",
        f"- Wiki Schema: {update.wiki.schema_version}",
        f"- Metadata Schema: {update.metadata.schema_version}",
        f"- Index Schema: {update.metadata.index_schema_version}",
    ]
    return "\n".join(lines) + "\n"


def _markdown_status(state: WikiState) -> str:
    result = _json_status(state)
    counts = cast(JsonObject, result["counts"])
    lines = [
        "# Wiki status",
        "",
        f"- Title: {json.dumps(state.wiki.title, ensure_ascii=False)}",
        f"- Language: `{state.metadata.output_language}`",
        f"- Complete: {str(result['complete']).lower()}",
    ]
    lines.extend(f"- {status.value}: {counts[status.value]}" for status in PageStatus)
    for section in state.wiki.sections:
        lines.extend(("", f"## {section.title}", ""))
        lines.extend(
            f"- `{page.id}` — {page.status.value} → {_next_action(page.status)}"
            for page in section.pages
        )
    return "\n".join(lines) + "\n"


def _markdown_evidence(update: WikiEvidenceUpdate) -> str:
    snapshot = update.page.evidence_snapshot
    if snapshot is None:  # pragma: no cover - service postcondition
        raise RuntimeError("Evidence update is missing its persisted snapshot")
    symbols: dict[str, Symbol] = {symbol.id: symbol for symbol in update.symbols}
    context = context_result_markdown(update.bundle, symbols=symbols)
    context = context.replace("# Repository context", "## Retrieved context", 1)
    lines = [
        "# Wiki evidence",
        "",
        f"- Page ID: `{update.page.id}`",
        f"- Status: `{update.page.status.value}`",
        f"- Generated at: `{snapshot.generated_at}`",
        f"- Index build: `{snapshot.index_build_id}`",
        "",
        context.rstrip("\n"),
    ]
    return "\n".join(lines) + "\n"


def _next_action(status: PageStatus) -> str:
    return {
        PageStatus.PENDING: "collect_evidence",
        PageStatus.EVIDENCE_READY: "generate_page",
        PageStatus.GENERATED: "complete",
        PageStatus.FAILED: "retry",
    }[status]


WIKI_COMMAND = Command(
    name="wiki",
    help="persist and inspect resumable repository Wiki state",
    configure=configure,
    handler=handle,
)

__all__ = ["MAX_STRUCTURE_INPUT_BYTES", "WIKI_COMMAND"]
