"""Lazy Tree-sitter adapter for JavaScript and TypeScript languages."""

from __future__ import annotations

import importlib
from bisect import bisect_right
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Protocol, cast

from repo_dive.parsing.models import (
    Chunk,
    ParseDiagnostic,
    ParseResult,
    Relationship,
    Symbol,
    create_chunk,
    create_relationship,
    create_symbol,
)
from repo_dive.parsing.text import TextParser
from repo_dive.scanner.models import FileRecord


class _Node(Protocol):
    type: str
    start_byte: int
    end_byte: int
    children: list[_Node]
    has_error: bool

    def child_by_field_name(self, name: str) -> _Node | None: ...


class _Tree(Protocol):
    root_node: _Node


class _Parser(Protocol):
    def parse(self, source: bytes) -> _Tree | None: ...


LanguageLoader = Callable[[str], _Parser]

_CLASS_NODE_TYPES = {"abstract_class_declaration", "class_declaration"}
_FUNCTION_NODE_TYPES = {
    "function_declaration",
    "generator_function_declaration",
}
_METHOD_NODE_TYPES = {"method_definition", "method_signature"}


class TreeSitterParser:
    """Parse one supported language while loading its grammar on demand."""

    def __init__(
        self,
        language: str,
        *,
        language_loader: LanguageLoader | None = None,
        fallback: TextParser | None = None,
    ) -> None:
        self._language = language
        self._language_loader = language_loader or _load_parser
        self._fallback = fallback or TextParser()

    def parse(self, file: FileRecord, text: str) -> ParseResult:
        """Parse text or return fallback chunks with a stable warning."""
        try:
            parser = self._language_loader(self._language)
            tree = parser.parse(text.encode("utf-8"))
        except (ImportError, AttributeError, OSError, RuntimeError, TypeError):
            return self._fallback_result(
                file,
                text,
                code="tree_sitter_unavailable",
                message="Tree-sitter grammar is unavailable; text fallback was used.",
            )
        if tree is None:
            return self._fallback_result(
                file,
                text,
                code="tree_sitter_parse_failed",
                message="Tree-sitter returned no parse tree; text fallback was used.",
            )

        collector = _TreeSymbolCollector(file.path, text)
        collector.collect(tree.root_node)
        diagnostics: tuple[ParseDiagnostic, ...] = ()
        if tree.root_node.has_error:
            diagnostics = (
                ParseDiagnostic(
                    code="tree_sitter_parse_error",
                    message="Tree-sitter reported one or more syntax errors.",
                    path=file.path,
                ),
            )
        if not collector.chunks and text.strip():
            fallback = self._fallback.parse(file, text)
            return ParseResult(
                chunks=fallback.chunks,
                symbols=collector.symbols,
                relationships=collector.relationships,
                diagnostics=diagnostics,
            )
        return ParseResult(
            chunks=collector.chunks,
            symbols=collector.symbols,
            relationships=collector.relationships,
            diagnostics=diagnostics,
        )

    def _fallback_result(
        self,
        file: FileRecord,
        text: str,
        *,
        code: str,
        message: str,
    ) -> ParseResult:
        fallback = self._fallback.parse(file, text)
        return ParseResult(
            chunks=fallback.chunks,
            diagnostics=(
                ParseDiagnostic(
                    code=code,
                    message=message,
                    path=file.path,
                ),
            ),
        )


class _TreeSymbolCollector:
    def __init__(self, path: str, text: str) -> None:
        self._path = path
        self._source = text.encode("utf-8")
        self._line_starts = _line_starts(self._source)
        self._lines = text.splitlines(keepends=True)
        module_name = _module_name(path)
        self._module = create_symbol(
            kind="module",
            name=module_name.rsplit(".", maxsplit=1)[-1],
            qualified_name=module_name,
            path=path,
            start_line=1,
            end_line=max(1, len(self._lines)),
        )
        self._symbols: list[Symbol] = [self._module]
        self._chunks: list[Chunk] = []
        self._relationships: list[Relationship] = []

    @property
    def symbols(self) -> tuple[Symbol, ...]:
        return tuple(self._symbols)

    @property
    def chunks(self) -> tuple[Chunk, ...]:
        return tuple(self._chunks)

    @property
    def relationships(self) -> tuple[Relationship, ...]:
        return tuple(self._relationships)

    def collect(self, root: _Node) -> None:
        pending = [(root, self._module)]
        while pending:
            node, parent = pending.pop()
            symbol = self._symbol_for_node(node, parent)
            scope = symbol or parent
            pending.extend((child, scope) for child in reversed(node.children))

    def _symbol_for_node(self, node: _Node, parent: Symbol) -> Symbol | None:
        kind: str | None = None
        if node.type in _CLASS_NODE_TYPES:
            kind = "class"
        elif node.type in _METHOD_NODE_TYPES:
            kind = "method"
        elif node.type in _FUNCTION_NODE_TYPES:
            kind = "function"
        if kind is None:
            return None

        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        name = self._source[name_node.start_byte : name_node.end_byte].decode("utf-8")
        start_line, end_line = _line_range(node, self._line_starts)
        symbol = create_symbol(
            kind=kind,
            name=name,
            qualified_name=f"{parent.qualified_name}.{name}",
            path=self._path,
            start_line=start_line,
            end_line=end_line,
        )
        self._symbols.append(symbol)
        self._chunks.append(
            create_chunk(
                path=self._path,
                start_line=start_line,
                end_line=end_line,
                text="".join(self._lines[start_line - 1 : end_line]),
                symbol_id=symbol.id,
            )
        )
        self._relationships.append(
            create_relationship(
                source_id=parent.id,
                target_id=symbol.id,
                kind="contains",
                confidence=1.0,
                source="tree_sitter",
            )
        )
        return symbol


def _load_parser(language: str) -> _Parser:
    tree_sitter = importlib.import_module("tree_sitter")
    language_class = tree_sitter.Language
    parser_class = tree_sitter.Parser

    if language in {"javascript", "jsx"}:
        grammar = importlib.import_module("tree_sitter_javascript")
        language_capsule = grammar.language()
    elif language in {"typescript", "tsx"}:
        grammar = importlib.import_module("tree_sitter_typescript")
        loader_name = "language_tsx" if language == "tsx" else "language_typescript"
        language_capsule = getattr(grammar, loader_name)()
    else:
        raise ImportError(f"Unsupported Tree-sitter language: {language}")

    loaded_language = language_class(language_capsule)
    return cast(_Parser, parser_class(loaded_language))


def _line_starts(source: bytes) -> tuple[int, ...]:
    return (0, *(index + 1 for index, byte in enumerate(source) if byte == 0x0A))


def _line_range(node: _Node, line_starts: tuple[int, ...]) -> tuple[int, int]:
    start_line = bisect_right(line_starts, node.start_byte)
    final_byte = max(node.start_byte, node.end_byte - 1)
    end_line = bisect_right(line_starts, final_byte)
    return start_line, max(start_line, end_line)


def _module_name(path: str) -> str:
    candidate = PurePosixPath(path)
    parts = list(candidate.with_suffix("").parts)
    if parts and parts[-1] == "index":
        parts.pop()
    return ".".join(parts) or candidate.stem
