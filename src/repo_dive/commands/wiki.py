"""Public resumable `repo-dive wiki` command boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
from repo_dive.storage.paths import resolve_repository
from repo_dive.wiki.legacy import (
    LegacyStructureUpdate,
    LegacyWikiService,
    legacy_structure_from_document,
)
from repo_dive.wiki.models import Metadata, PageStatus
from repo_dive.wiki.service import (
    StructureUpdate,
    WikiBuildUpdate,
    WikiEvidenceUpdate,
    WikiPageUpdate,
    WikiService,
    WikiState,
)
from repo_dive.wiki.submission import (
    PAGE_SUBMISSION_SCHEMA_VERSION,
    page_submission_from_document,
)

MAX_STRUCTURE_INPUT_BYTES = 1_000_000
MAX_PAGE_INPUT_BYTES = 1_500_000


def configure(parser: argparse.ArgumentParser) -> None:
    """Configure explicit non-interactive Wiki subcommands."""
    subparsers = parser.add_subparsers(dest="wiki_command", required=True)

    classify_parser = subparsers.add_parser(
        "classify", help="classify the current index for governed Wiki composition"
    )
    classify_parser.add_argument("repository", help="local repository directory")
    classify_parser.add_argument(
        "--template",
        metavar="ID",
        help="registered primary template override",
    )
    _add_format(classify_parser)
    classify_parser.set_defaults(_wiki_handler=_handle_classify)

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

    init_parser = subparsers.add_parser(
        "init",
        help="initialize governed Wiki Schema 2.0 from classification and templates",
    )
    init_parser.add_argument("repository", help="local repository directory")
    init_parser.add_argument(
        "--locale",
        required=True,
        choices=("en", "zh-CN", "ja"),
        help="exact output locale",
    )
    init_parser.add_argument(
        "--template",
        metavar="ID",
        help="registered primary template override",
    )
    _add_format(init_parser)
    init_parser.set_defaults(_wiki_handler=_handle_init)

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

    page_parser = subparsers.add_parser(
        "page",
        help="validate and persist one agent-generated Wiki page",
    )
    page_parser.add_argument("repository", help="local repository directory")
    page_parser.add_argument(
        "--page",
        required=True,
        type=_page_id,
        metavar="PAGE_ID",
        help="stable Page ID from the persisted Wiki structure",
    )
    page_parser.add_argument(
        "--input",
        required=True,
        metavar="PATH|-",
        help="UTF-8 JSON page input file, or - for stdin",
    )
    _add_format(page_parser)
    page_parser.set_defaults(_wiki_handler=_handle_page)

    build_parser = subparsers.add_parser(
        "build",
        help="validate and atomically assemble the current Wiki Markdown",
    )
    build_parser.add_argument("repository", help="local repository directory")
    _add_format(build_parser)
    build_parser.set_defaults(_wiki_handler=_handle_build)

    status_parser = subparsers.add_parser(
        "status",
        help="report resumable Wiki page states and next actions",
    )
    status_parser.add_argument("repository", help="local repository directory")
    _add_format(status_parser)
    status_parser.set_defaults(_wiki_handler=_handle_status)

    validate_parser = subparsers.add_parser(
        "validate", help="validate governed Wiki Schema 2.0 state without publication"
    )
    validate_parser.add_argument("repository", help="local repository directory")
    _add_format(validate_parser)
    validate_parser.set_defaults(_wiki_handler=_handle_validate)


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
    if document.get("schema_version") != "1.0":
        raise InvocationError(
            "wiki_structure_version_unsupported",
            "Deprecated wiki structure accepts only its original Schema 1.0 input; "
            "use wiki init for governed Schema 2.0 state.",
            details={"actual": document.get("schema_version"), "expected": "1.0"},
        )
    try:
        structure = legacy_structure_from_document(document)
    except (KeyError, TypeError, ValueError) as error:
        raise InvocationError(
            "wiki_structure_invalid",
            "Wiki structure input does not match deprecated Schema 1.0.",
        ) from error
    update = LegacyWikiService(args.repository).apply_structure(structure)
    output_format: OutputFormat = args.format
    output = (
        _markdown_legacy_structure(update)
        if output_format == "markdown"
        else _json_legacy_structure(update)
    )
    return CommandOutput(
        command="wiki structure",
        format=output_format,
        result=output,
        repository=update.metadata.repository,
    )


def _handle_classify(args: argparse.Namespace) -> CommandOutput:
    result = WikiService(args.repository).classify(template_override=args.template)
    output_format: OutputFormat = args.format
    output: JsonObject | str = (
        {"classification": result.to_document()}
        if output_format == "json"
        else _markdown_classification(result.to_document())
    )
    return CommandOutput(
        command="wiki classify",
        format=output_format,
        result=output,
        repository=str(resolve_repository(args.repository)),
    )


def _handle_init(args: argparse.Namespace) -> CommandOutput:
    update = WikiService(args.repository).initialize_governed(
        locale=args.locale, template_override=args.template
    )
    output_format: OutputFormat = args.format
    output = (
        _markdown_structure(update)
        if output_format == "markdown"
        else _json_structure(update)
    )
    return CommandOutput(
        command="wiki init",
        format=output_format,
        result=output,
        repository=update.metadata.repository,
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


def _handle_validate(args: argparse.Namespace) -> CommandOutput:
    state = WikiService(args.repository).validate_wiki()
    page_count = sum(len(section.pages) for section in state.wiki.sections)
    result: JsonObject = {
        **_governance_document(state.metadata),
        "page_count": page_count,
        "schema_version": state.wiki.schema_version,
        "subsection_count": sum(
            len(page.subsections)
            for section in state.wiki.sections
            for page in section.pages
        ),
        "valid": True,
    }
    output_format: OutputFormat = args.format
    output: JsonObject | str = (
        result if output_format == "json" else "# Wiki validation\n\n- Valid: true\n"
    )
    return CommandOutput(
        command="wiki validate",
        format=output_format,
        result=output,
        repository=state.metadata.repository,
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


def _handle_page(args: argparse.Namespace) -> CommandOutput:
    document = _read_page_document(args.input)
    try:
        submission = page_submission_from_document(document)
    except (KeyError, TypeError, ValueError) as error:
        raise InvocationError(
            "wiki_page_invalid",
            "Wiki page input does not match the required Schema.",
        ) from error
    update = WikiService(args.repository).submit_page(args.page, submission)
    output_format: OutputFormat = args.format
    output = (
        _markdown_page(update) if output_format == "markdown" else _json_page(update)
    )
    return CommandOutput(
        command="wiki page",
        format=output_format,
        result=output,
        repository=update.metadata.repository,
    )


def _handle_build(args: argparse.Namespace) -> CommandOutput:
    update = WikiService(args.repository).build_wiki()
    output_format: OutputFormat = args.format
    output = update.markdown if output_format == "markdown" else _json_build(update)
    return CommandOutput(
        command="wiki build",
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
    if isinstance(actual_version, str) and actual_version not in {
        "1.0",
        "2.0",
    }:
        raise InvocationError(
            "wiki_structure_version_unsupported",
            "Wiki structure input version is not supported.",
            details={
                "actual": actual_version,
                "expected": "1.0",
            },
        )
    return document


def _read_page_document(input_path: str) -> JsonObject:
    try:
        if input_path == "-":
            stream = getattr(sys.stdin, "buffer", sys.stdin)
            raw = stream.read(MAX_PAGE_INPUT_BYTES + 1)
        else:
            with Path(input_path).open("rb") as stream:
                raw = stream.read(MAX_PAGE_INPUT_BYTES + 1)
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        if len(data) > MAX_PAGE_INPUT_BYTES:
            raise InvocationError(
                "wiki_page_input_too_large",
                "Wiki page input exceeds the supported size.",
                details={"max_bytes": MAX_PAGE_INPUT_BYTES},
            )
        value = json.loads(data.decode("utf-8"))
    except InvocationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InvocationError(
            "wiki_page_input_invalid",
            "Wiki page input is unavailable or invalid JSON.",
        ) from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise InvocationError(
            "wiki_page_input_invalid",
            "Wiki page input must be a JSON object.",
        )
    document = cast(JsonObject, value)
    actual_version = document.get("schema_version")
    if (
        isinstance(actual_version, str)
        and actual_version != PAGE_SUBMISSION_SCHEMA_VERSION
    ):
        raise InvocationError(
            "wiki_page_version_unsupported",
            "Wiki page input version is not supported.",
            details={
                "actual": actual_version,
                "expected": PAGE_SUBMISSION_SCHEMA_VERSION,
            },
        )
    return document


def _json_structure(update: StructureUpdate) -> JsonObject:
    page_count = sum(len(section.pages) for section in update.wiki.sections)
    return {
        **_governance_document(update.metadata),
        "changed": update.changed,
        "created_page_ids": list(update.created_page_ids),
        "index_build_id": update.metadata.index_build_id,
        "index_schema_version": update.metadata.index_schema_version,
        "invalidated_page_ids": list(update.invalidated_page_ids),
        "metadata_schema_version": update.metadata.schema_version,
        "page_count": page_count,
        "preserved_page_ids": list(update.preserved_page_ids),
        "section_count": len(update.wiki.sections),
        "subsection_count": sum(
            len(page.subsections)
            for section in update.wiki.sections
            for page in section.pages
        ),
        "source_commit": update.metadata.source_commit,
        "source_control": update.metadata.source_control,
        "source_dirty": update.metadata.source_dirty,
        "wiki_schema_version": update.wiki.schema_version,
    }


def _json_legacy_structure(update: LegacyStructureUpdate) -> JsonObject:
    return {
        "changed": update.changed,
        "created_page_ids": list(update.created_page_ids),
        "index_build_id": update.metadata.index_build_id,
        "index_schema_version": update.metadata.index_schema_version,
        "invalidated_page_ids": list(update.invalidated_page_ids),
        "metadata_schema_version": update.metadata.schema_version,
        "page_count": sum(len(section.pages) for section in update.wiki.sections),
        "preserved_page_ids": list(update.preserved_page_ids),
        "section_count": len(update.wiki.sections),
        "source_commit": update.metadata.source_commit,
        "wiki_schema_version": update.wiki.schema_version,
    }


def _json_status(state: WikiState) -> JsonObject:
    counts = Counter(
        page.status for section in state.wiki.sections for page in section.pages
    )
    page_count = sum(counts.values())
    return {
        **_governance_document(state.metadata),
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
                        "citation_count": len(page.citation_ids),
                        "evidence_count": len(page.evidence),
                        "has_body": bool(page.subsection_contents),
                        "has_error": page.error is not None,
                        "id": page.id,
                        "next_action": _next_action(page.status),
                        "status": page.status.value,
                        "subsections": [
                            {
                                "description": subsection.description,
                                "direct_source_paths": list(
                                    subsection.direct_source_paths
                                ),
                                "documentation_only": subsection.documentation_only,
                                "generated": any(
                                    content.subsection_id == subsection.id
                                    for content in page.subsection_contents
                                ),
                                "id": subsection.id,
                                "title": subsection.title,
                            }
                            for subsection in page.subsections
                        ],
                        "title": page.title,
                    }
                    for page in section.pages
                ],
                "title": section.title,
            }
            for section in state.wiki.sections
        ],
        "title": state.wiki.title,
        "source_commit": state.metadata.source_commit,
        "source_control": state.metadata.source_control,
        "source_dirty": state.metadata.source_dirty,
        "subsection_count": sum(
            len(page.subsections)
            for section in state.wiki.sections
            for page in section.pages
        ),
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
        reference = next(
            value
            for value in update.page.evidence
            if value.evidence_id == item.evidence_id
        )
        item_document["role"] = reference.role
        item_document["subsection_ids"] = list(reference.subsection_ids)
        item_document["direct_paths"] = list(reference.direct_paths)
        items.append(item_document)
    return {
        **_governance_document(update.metadata),
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
        "page_contract": {
            "description": update.page.description,
            "id": update.page.id,
            "relevant_files": list(update.page.relevant_files),
            "subsections": [item.to_document() for item in update.page.subsections],
            "title": update.page.title,
        },
        "query": context["query"],
        "repository_fingerprint": snapshot.repository_fingerprint,
        "reserved_tokens": context["reserved_tokens"],
        "result_count": context["result_count"],
        "status": update.page.status.value,
        "token_budget": context["token_budget"],
        "truncated": context["truncated"],
    }


def _json_page(update: WikiPageUpdate) -> JsonObject:
    body_bytes = sum(
        len(content.body.encode("utf-8")) for content in update.page.subsection_contents
    )
    return {
        **_governance_document(update.metadata),
        "body_bytes": body_bytes,
        "changed": update.changed,
        "citation_count": len(update.page.citation_ids),
        "evidence_ids": list(update.page.citation_ids),
        "page_id": update.page.id,
        "status": update.page.status.value,
    }


def _json_build(update: WikiBuildUpdate) -> JsonObject:
    data = update.markdown.encode("utf-8")
    return {
        **_governance_document(update.metadata),
        "artifact_path": update.artifact_path,
        "bytes": len(data),
        "changed": update.changed,
        "page_count": sum(len(section.pages) for section in update.wiki.sections),
        "section_count": len(update.wiki.sections),
        "sha256": hashlib.sha256(data).hexdigest(),
        "source_count": sum(
            len(page.citation_ids)
            for section in update.wiki.sections
            for page in section.pages
        ),
        "source_commit": update.metadata.source_commit,
        "source_control": update.metadata.source_control,
        "source_dirty": update.metadata.source_dirty,
        "index_build_id": update.metadata.index_build_id,
        "repository_fingerprint": update.metadata.repository_fingerprint,
    }


def _governance_document(metadata: Metadata) -> JsonObject:
    repository_classification = metadata.repository_classification
    template = metadata.template
    if repository_classification is None or template is None:
        return {}
    return {
        "classification": repository_classification.to_document(),
        "template": template.to_document(),
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


def _markdown_legacy_structure(update: LegacyStructureUpdate) -> str:
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


def _markdown_classification(classification: JsonObject) -> str:
    detected = cast(JsonObject, classification["detected_primary"])
    effective = cast(JsonObject, classification["effective_primary"])
    topology = cast(JsonObject, classification["topology"])
    return "\n".join(
        (
            "# Wiki classification",
            "",
            f"- Detected primary: `{detected['id']}`",
            f"- Effective primary: `{effective['id']}`",
            f"- Topology: `{topology['id']}`",
            f"- Selection source: `{classification['selection_source']}`",
            f"- Index build: `{classification['index_build_id']}`",
            "",
        )
    )


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


def _markdown_page(update: WikiPageUpdate) -> str:
    body_bytes = sum(
        len(content.body.encode("utf-8")) for content in update.page.subsection_contents
    )
    lines = [
        "# Wiki page",
        "",
        f"- Page ID: `{update.page.id}`",
        f"- Status: `{update.page.status.value}`",
        f"- Changed: {str(update.changed).lower()}",
        f"- Body bytes: {body_bytes}",
        f"- Subsections: {len(update.page.subsection_contents)}",
        f"- Citations: {len(update.page.citation_ids)}",
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

__all__ = ["MAX_PAGE_INPUT_BYTES", "MAX_STRUCTURE_INPUT_BYTES", "WIKI_COMMAND"]
