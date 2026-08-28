"""Public read-only `repo-dive search` command boundary."""

from __future__ import annotations

import argparse
import json

from repo_dive.commands import Command, CommandOutput, OutputFormat
from repo_dive.errors import RepositoryError
from repo_dive.indexing.graph import SymbolGraph
from repo_dive.indexing.service import load_published_index
from repo_dive.indexing.store import IndexStore
from repo_dive.parsing.models import Symbol
from repo_dive.retrieval.fusion import FusionResult, SearchHit, fuse_hits
from repo_dive.retrieval.lexical import search_lexical
from repo_dive.retrieval.structural import search_structural
from repo_dive.schema import JsonObject

DEFAULT_MAX_RESULTS = 10
MAX_RESULTS = 50
MAX_QUERY_LENGTH = 1_000
CANDIDATE_MULTIPLIER = 4
MAX_CANDIDATES = MAX_RESULTS * CANDIDATE_MULTIPLIER


def configure(parser: argparse.ArgumentParser) -> None:
    """Configure bounded, non-interactive search arguments."""
    parser.add_argument("repository", help="local repository directory")
    parser.add_argument("query", type=_query, help="code or symbol search query")
    parser.add_argument(
        "--max-results",
        type=_result_limit,
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
    published = load_published_index(args.repository)
    candidate_limit = min(args.max_results * CANDIDATE_MULTIPLIER, MAX_CANDIDATES)

    with IndexStore.open_readonly(published.database) as store:
        chunks = store.get_chunks()
        bm25_index = store.get_bm25_index()
        if bm25_index is None:
            raise RepositoryError(
                "index_incomplete",
                "Repository index does not contain lexical search data.",
                details={"build_id": published.manifest.build_id},
            )
        lexical_hits = search_lexical(
            args.query,
            index=bm25_index,
            chunks=chunks,
            max_results=candidate_limit,
        )
        structural_hits = search_structural(
            args.query,
            graph=SymbolGraph(store),
            chunks=chunks,
            max_results=candidate_limit,
            max_nodes=MAX_CANDIDATES,
            max_edges=MAX_CANDIDATES * 4,
        )
        fused = fuse_hits(
            lexical_hits=lexical_hits,
            structural_hits=structural_hits,
            max_results=args.max_results,
        )
        symbol_ids = tuple(
            dict.fromkeys(
                hit.chunk.symbol_id
                for hit in fused.hits
                if hit.chunk.symbol_id is not None
            )
        )
        symbols = {symbol.id: symbol for symbol in store.get_symbols_by_id(symbol_ids)}

    output_format: OutputFormat = args.format
    output = (
        _markdown_result(args.query, fused, symbols=symbols)
        if output_format == "markdown"
        else _json_result(
            args.query,
            fused,
            max_results=args.max_results,
            symbols=symbols,
        )
    )
    return CommandOutput(
        command="search",
        format=output_format,
        result=output,
        repository=str(published.repository),
    )


def _query(value: str) -> str:
    query = value.strip()
    if not query:
        raise argparse.ArgumentTypeError("query must not be empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise argparse.ArgumentTypeError(
            f"query must not exceed {MAX_QUERY_LENGTH} characters"
        )
    return query


def _result_limit(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be an integer") from error
    if not 1 <= parsed <= MAX_RESULTS:
        raise argparse.ArgumentTypeError(f"value must be from 1 to {MAX_RESULTS}")
    return parsed


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
