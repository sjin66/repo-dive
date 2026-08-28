"""Public read-only `repo-dive search` command boundary."""

from __future__ import annotations

import argparse
import json

from repo_dive.commands import Command, CommandOutput, OutputFormat
from repo_dive.commands.retrieval_arguments import query_value, result_limit
from repo_dive.parsing.models import Symbol
from repo_dive.retrieval.fusion import FusionResult, SearchHit
from repo_dive.retrieval.service import (
    DEFAULT_MAX_RESULTS,
    MAX_RESULTS,
    search_repository,
)
from repo_dive.schema import JsonObject


def configure(parser: argparse.ArgumentParser) -> None:
    """Configure bounded, non-interactive search arguments."""
    parser.add_argument("repository", help="local repository directory")
    parser.add_argument("query", type=query_value, help="code or symbol search query")
    parser.add_argument(
        "--max-results",
        type=result_limit,
        default=DEFAULT_MAX_RESULTS,
        metavar="COUNT",
        help=f"maximum returned hits, from 1 to {MAX_RESULTS}",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="result output format (default: json)",
    )


def handle(args: argparse.Namespace) -> CommandOutput:
    """Query a validated current index without changing repository artifacts."""
    retrieved = search_repository(
        args.repository,
        args.query,
        max_results=args.max_results,
    )
    symbols = {symbol.id: symbol for symbol in retrieved.symbols}

    output_format: OutputFormat = args.format
    output = (
        _markdown_result(args.query, retrieved.fusion, symbols=symbols)
        if output_format == "markdown"
        else _json_result(
            args.query,
            retrieved.fusion,
            max_results=args.max_results,
            symbols=symbols,
        )
    )
    return CommandOutput(
        command="search",
        format=output_format,
        result=output,
        repository=str(retrieved.repository),
    )


def _json_result(
    query: str,
    result: FusionResult,
    *,
    max_results: int,
    symbols: dict[str, Symbol],
) -> JsonObject:
    metadata = result.metadata
    channel_weights: JsonObject = dict(metadata.channel_weights)
    fusion: JsonObject = {
        "channel_weights": channel_weights,
        "overlap_threshold": metadata.overlap_threshold,
        "rrf_k": metadata.rrf_k,
        "strategy": metadata.strategy,
    }
    return {
        "fusion": fusion,
        "hits": [_json_hit(hit, symbols=symbols) for hit in result.hits],
        "max_results": max_results,
        "query": query,
        "result_count": len(result.hits),
    }


def _json_hit(hit: SearchHit, *, symbols: dict[str, Symbol]) -> JsonObject:
    symbol = (
        symbols.get(hit.chunk.symbol_id) if hit.chunk.symbol_id is not None else None
    )
    return {
        "chunk_id": hit.chunk.id,
        "end_line": hit.chunk.end_line,
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
    query: str,
    result: FusionResult,
    *,
    symbols: dict[str, Symbol],
) -> str:
    lines = [
        "# Repository search",
        "",
        f"- Query: {json.dumps(query, ensure_ascii=False)}",
        f"- Results: {len(result.hits)}",
        f"- Fusion: {result.metadata.strategy}",
        f"- RRF k: {result.metadata.rrf_k}",
    ]
    for index, hit in enumerate(result.hits, start=1):
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


SEARCH_COMMAND = Command(
    name="search",
    help="query a current local repository index without modifying it",
    configure=configure,
    handler=handle,
)

__all__ = ["MAX_RESULTS", "SEARCH_COMMAND"]
