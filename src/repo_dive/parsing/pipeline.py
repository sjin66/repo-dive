"""Unified parsing pipeline and output normalization."""

from __future__ import annotations

from repo_dive.parsing.models import (
    Chunk,
    ParseDiagnostic,
    ParseResult,
    Relationship,
    Symbol,
    create_chunk,
)
from repo_dive.parsing.registry import ParserRegistry
from repo_dive.scanner.models import ReadStatus, SourceFile

DEFAULT_MAX_CHUNK_LINES = 200


class ParsingPipeline:
    """Select, run, split, de-duplicate, and order parser results."""

    def __init__(
        self,
        *,
        registry: ParserRegistry | None = None,
        max_chunk_lines: int = DEFAULT_MAX_CHUNK_LINES,
    ) -> None:
        if max_chunk_lines <= 0:
            raise ValueError("max_chunk_lines must be greater than zero")
        self._registry = registry or ParserRegistry()
        self._max_chunk_lines = max_chunk_lines

    def parse(self, source: SourceFile) -> ParseResult:
        """Parse one scanned source file into normalized domain objects."""
        if source.record.status is not ReadStatus.READ or source.text is None:
            return ParseResult(
                diagnostics=(
                    ParseDiagnostic(
                        code="source_not_readable",
                        message="Source file was skipped during repository scanning.",
                        path=source.record.path,
                    ),
                )
            )

        parser = self._registry.parser_for(source.record)
        result = parser.parse(source.record, source.text)
        chunks = _normalize_chunks(
            result.chunks,
            source.text,
            max_chunk_lines=self._max_chunk_lines,
        )
        symbols = _normalize_symbols(result.symbols)
        relationships = _normalize_relationships(result.relationships)
        diagnostics = tuple(
            sorted(
                result.diagnostics,
                key=lambda item: (item.path, item.line or 0, item.code),
            )
        )
        return ParseResult(
            chunks=chunks,
            symbols=symbols,
            relationships=relationships,
            diagnostics=diagnostics,
        )


def _normalize_chunks(
    chunks: tuple[Chunk, ...], source_text: str, *, max_chunk_lines: int
) -> tuple[Chunk, ...]:
    lines = source_text.splitlines(keepends=True)
    normalized: dict[str, Chunk] = {}
    for chunk in chunks:
        start_line = chunk.start_line
        while start_line <= chunk.end_line:
            end_line = min(start_line + max_chunk_lines - 1, chunk.end_line)
            split_chunk = create_chunk(
                path=chunk.path,
                start_line=start_line,
                end_line=end_line,
                text="".join(lines[start_line - 1 : end_line]),
                symbol_id=chunk.symbol_id,
            )
            normalized[split_chunk.id] = split_chunk
            start_line = end_line + 1
    return tuple(
        sorted(
            normalized.values(),
            key=lambda item: (item.path, item.start_line, item.end_line, item.id),
        )
    )


def _normalize_symbols(symbols: tuple[Symbol, ...]) -> tuple[Symbol, ...]:
    unique = {symbol.id: symbol for symbol in symbols}
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (item.path, item.start_line, item.end_line, item.id),
        )
    )


def _normalize_relationships(
    relationships: tuple[Relationship, ...],
) -> tuple[Relationship, ...]:
    unique = {
        (item.source_id, item.target_id, item.kind, item.source): item
        for item in relationships
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (item.source_id, item.kind, item.target_id, item.source),
        )
    )
