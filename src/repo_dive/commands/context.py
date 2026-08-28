"""Public read-only `repo-dive context` command boundary."""

from __future__ import annotations

import argparse
import json
from collections import Counter

from repo_dive.commands import Command, CommandOutput, OutputFormat
from repo_dive.commands.retrieval_arguments import query_value, result_limit
from repo_dive.context import EvidenceBundle, EvidenceItem, EvidencePacker
from repo_dive.context.packer import ExclusionReason
from repo_dive.parsing.models import Symbol
from repo_dive.retrieval.fusion import FusionMetadata
from repo_dive.retrieval.service import DEFAULT_MAX_RESULTS, search_repository
from repo_dive.schema import JsonObject


def configure(parser: argparse.ArgumentParser) -> None:
    """Configure bounded context-retrieval and output arguments."""
    parser.add_argument("repository", help="local repository directory")
    parser.add_argument(
        "query",
        type=query_value,
        help="question, code concept, or symbol to ground",
    )
    parser.add_argument(
        "--token-budget",
        type=_positive_integer,
        required=True,
        metavar="TOKENS",
        help="positive estimated-token budget for the complete evidence bundle",
    )
    parser.add_argument(
        "--max-results",
        type=result_limit,
        default=DEFAULT_MAX_RESULTS,
        metavar="COUNT",
        help="maximum retrieval candidates before budget packing",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="result output format (default: json)",
    )


def handle(args: argparse.Namespace) -> CommandOutput:
    """Retrieve and pack complete evidence without mutating the index."""
    retrieved = search_repository(
        args.repository,
        args.query,
        max_results=args.max_results,
    )
    bundle = EvidencePacker().pack(
        args.query,
        retrieved.fusion.hits,
        token_budget=args.token_budget,
    )
    symbols = {symbol.id: symbol for symbol in retrieved.symbols}
    output_format: OutputFormat = args.format
    output = (
        _markdown_result(bundle, symbols=symbols)
        if output_format == "markdown"
        else _json_result(
            bundle,
            fusion=retrieved.fusion.metadata,
            max_results=args.max_results,
            symbols=symbols,
        )
    )
    return CommandOutput(
        command="context",
        format=output_format,
        result=output,
        repository=str(retrieved.repository),
    )


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _json_result(
    bundle: EvidenceBundle,
    *,
    fusion: FusionMetadata,
    max_results: int,
    symbols: dict[str, Symbol],
) -> JsonObject:
    return {
        "estimated_tokens": bundle.estimated_tokens,
        "estimator": bundle.estimator,
        "excluded": _excluded_summary(bundle),
        "fusion": _json_fusion(fusion),
        "items": [_json_item(item, symbols=symbols) for item in bundle.items],
        "max_results": max_results,
        "query": bundle.query,
        "reserved_tokens": bundle.reserved_tokens,
        "result_count": len(bundle.items),
        "token_budget": bundle.token_budget,
        "truncated": bundle.truncated,
    }


def _excluded_summary(bundle: EvidenceBundle) -> JsonObject:
    counts = Counter(item.reason for item in bundle.excluded)
    return {reason.value: counts[reason] for reason in ExclusionReason}


def _json_fusion(metadata: FusionMetadata) -> JsonObject:
    return {
        "channel_weights": dict(metadata.channel_weights),
        "overlap_threshold": metadata.overlap_threshold,
        "rrf_k": metadata.rrf_k,
        "strategy": metadata.strategy,
    }


def _json_item(
    item: EvidenceItem,
    *,
    symbols: dict[str, Symbol],
) -> JsonObject:
    hit = item.hit
    symbol = (
        symbols.get(hit.chunk.symbol_id) if hit.chunk.symbol_id is not None else None
    )
    return {
        "chunk_id": hit.chunk.id,
        "end_line": hit.chunk.end_line,
        "estimated_tokens": item.estimated_tokens,
        "evidence_id": item.evidence_id,
        "fused_score": hit.fused_score,
        "lexical_score": hit.lexical_score,
        "path": hit.chunk.path,
        "reasons": list(hit.reasons),
        "start_line": hit.chunk.start_line,
        "structural_score": hit.structural_score,
        "symbol": _json_symbol(symbol),
        "text": hit.chunk.text,
        "vector_score": hit.vector_score,
    }


def _json_symbol(symbol: Symbol | None) -> JsonObject | None:
    if symbol is None:
        return None
    return {
        "id": symbol.id,
        "kind": symbol.kind,
        "name": symbol.name,
        "qualified_name": symbol.qualified_name,
    }


def _markdown_result(
    bundle: EvidenceBundle,
    *,
    symbols: dict[str, Symbol],
) -> str:
    exclusions = _excluded_summary(bundle)
    lines = [
        "# Repository context",
        "",
        f"- Query: {json.dumps(bundle.query, ensure_ascii=False)}",
        f"- Token budget: {bundle.token_budget}",
        f"- Estimated tokens: {bundle.estimated_tokens}",
        f"- Reserved tokens: {bundle.reserved_tokens}",
        f"- Estimator: `{bundle.estimator}`",
        f"- Truncated: {str(bundle.truncated).lower()}",
        f"- Results: {len(bundle.items)}",
        "- Excluded: "
        + ", ".join(
            f"{reason.value}={exclusions[reason.value]}" for reason in ExclusionReason
        ),
    ]
    for index, item in enumerate(bundle.items, start=1):
        hit = item.hit
        symbol = (
            symbols.get(hit.chunk.symbol_id)
            if hit.chunk.symbol_id is not None
            else None
        )
        location = json.dumps(hit.chunk.path, ensure_ascii=False)
        lines.extend(
            (
                "",
                f"## {index}. {location}:{hit.chunk.start_line}-{hit.chunk.end_line}",
                "",
                f"- Evidence ID: `{item.evidence_id}`",
                f"- Estimated tokens: {item.estimated_tokens}",
                f"- Symbol: {_format_symbol(symbol)}",
                f"- Lexical score: {_format_score(hit.lexical_score)}",
                f"- Structural score: {_format_score(hit.structural_score)}",
                f"- Vector score: {_format_score(hit.vector_score)}",
                f"- Fused score: {_format_score(hit.fused_score)}",
                "- Reasons:",
            )
        )
        lines.extend(
            f"  - {json.dumps(reason, ensure_ascii=False)}" for reason in hit.reasons
        )
        lines.extend(("", "### Source", ""))
        source_lines = hit.chunk.text.rstrip("\n").splitlines() or [""]
        lines.extend(f"    {line}" for line in source_lines)
    return "\n".join(lines) + "\n"


def _format_score(score: float | None) -> str:
    return "n/a" if score is None else f"{score:.12f}"


def _format_symbol(symbol: Symbol | None) -> str:
    if symbol is None:
        return "n/a"
    return json.dumps(symbol.qualified_name, ensure_ascii=False)


CONTEXT_COMMAND = Command(
    name="context",
    help="pack grounded repository evidence within a token budget",
    configure=configure,
    handler=handle,
)

__all__ = ["CONTEXT_COMMAND"]
