"""Python standard-library AST parser adapter."""

from __future__ import annotations

import ast
from pathlib import PurePosixPath

from repo_dive.parsing.models import (
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

_DefinitionNode = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


class PythonAstParser:
    """Extract Python symbols and structural relationships without I/O."""

    def __init__(self, *, fallback: TextParser | None = None) -> None:
        self._fallback = fallback or TextParser()

    def parse(self, file: FileRecord, text: str) -> ParseResult:
        """Parse a Python source record, falling back on syntax errors."""
        try:
            tree = ast.parse(text, filename=file.path)
        except SyntaxError as error:
            fallback_result = self._fallback.parse(file, text)
            diagnostic = ParseDiagnostic(
                code="python_syntax_error",
                message=error.msg,
                path=file.path,
                line=error.lineno,
            )
            return ParseResult(
                chunks=fallback_result.chunks,
                diagnostics=(diagnostic,),
            )

        lines = text.splitlines(keepends=True)
        definitions = _DefinitionCollector(file.path, len(lines))
        definitions.visit(tree)
        relationships = _RelationshipCollector(definitions)
        relationships.visit(tree)

        definition_symbols = tuple(
            symbol for symbol in definitions.symbols if symbol.kind != "module"
        )
        chunks = tuple(
            create_chunk(
                path=file.path,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                text="".join(lines[symbol.start_line - 1 : symbol.end_line]),
                symbol_id=symbol.id,
            )
            for symbol in definition_symbols
        )
        if not chunks and text.strip():
            chunks = self._fallback.parse(file, text).chunks

        symbols = tuple(
            sorted(
                (*definitions.symbols, *relationships.reference_symbols),
                key=_symbol_sort_key,
            )
        )
        edges = tuple(sorted(relationships.edges, key=_relationship_sort_key))
        return ParseResult(chunks=chunks, symbols=symbols, relationships=edges)


class _DefinitionCollector(ast.NodeVisitor):
    def __init__(self, path: str, line_count: int) -> None:
        self.path = path
        module_name = _module_name(path)
        module_symbol = create_symbol(
            kind="module",
            name=module_name.rsplit(".", maxsplit=1)[-1],
            qualified_name=module_name,
            path=path,
            start_line=1,
            end_line=max(1, line_count),
        )
        self.symbols: list[Symbol] = [module_symbol]
        self.symbol_by_node: dict[ast.AST, Symbol] = {}
        self.relationships: list[Relationship] = []
        self._scope: list[Symbol] = [module_symbol]

    @property
    def module(self) -> Symbol:
        return self._scope[0]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_definition(node, kind="class")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        kind = "method" if self._scope[-1].kind == "class" else "function"
        self._visit_definition(node, kind=kind)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        kind = "method" if self._scope[-1].kind == "class" else "function"
        self._visit_definition(node, kind=kind)

    def _visit_definition(self, node: _DefinitionNode, *, kind: str) -> None:
        parent = self._scope[-1]
        start_line = min(
            (decorator.lineno for decorator in node.decorator_list),
            default=node.lineno,
        )
        symbol = create_symbol(
            kind=kind,
            name=node.name,
            qualified_name=f"{parent.qualified_name}.{node.name}",
            path=self.path,
            start_line=start_line,
            end_line=node.end_lineno or node.lineno,
        )
        self.symbols.append(symbol)
        self.symbol_by_node[node] = symbol
        self.relationships.append(
            create_relationship(
                source_id=parent.id,
                target_id=symbol.id,
                kind="contains",
                confidence=1.0,
                source="python_ast",
            )
        )
        self._scope.append(symbol)
        self.generic_visit(node)
        self._scope.pop()


class _RelationshipCollector(ast.NodeVisitor):
    def __init__(self, definitions: _DefinitionCollector) -> None:
        self._definitions = definitions
        self._scope: list[Symbol] = [definitions.module]
        self._aliases: list[dict[str, str]] = [{}]
        self._references: dict[tuple[str, str, int], Symbol] = {}
        self._edges: dict[tuple[str, str, str], Relationship] = {
            (edge.source_id, edge.target_id, edge.kind): edge
            for edge in definitions.relationships
        }
        self._definitions_by_qualified_name = {
            symbol.qualified_name: symbol for symbol in definitions.symbols
        }
        self._definitions_by_name: dict[str, list[Symbol]] = {}
        for symbol in definitions.symbols:
            self._definitions_by_name.setdefault(symbol.name, []).append(symbol)

    @property
    def reference_symbols(self) -> tuple[Symbol, ...]:
        return tuple(self._references.values())

    @property
    def edges(self) -> tuple[Relationship, ...]:
        return tuple(self._edges.values())

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        symbol = self._definitions.symbol_by_node[node]
        for base in node.bases:
            name = _expression_name(base)
            if name is not None:
                target, confidence = self._target(name, line=base.lineno)
                self._add_edge(symbol, target, "inherits", confidence)
        self._visit_definition(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".", maxsplit=1)[0]
            self._aliases[-1][local_name] = alias.name if alias.asname else local_name
            target = self._reference("import", alias.name, node.lineno)
            self._add_edge(self._scope[-1], target, "imports", 1.0)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = f"{'.' * node.level}{node.module or ''}"
        for alias in node.names:
            qualified_name = f"{module}.{alias.name}" if module else alias.name
            local_name = alias.asname or alias.name
            self._aliases[-1][local_name] = qualified_name
            target = self._reference("import", qualified_name, node.lineno)
            self._add_edge(self._scope[-1], target, "imports", 1.0)

    def visit_Call(self, node: ast.Call) -> None:
        name = _expression_name(node.func)
        if name is not None:
            target, confidence = self._target(name, line=node.lineno)
            self._add_edge(self._scope[-1], target, "calls", confidence)
        self.generic_visit(node)

    def _visit_definition(self, node: _DefinitionNode) -> None:
        symbol = self._definitions.symbol_by_node[node]
        self._scope.append(symbol)
        self._aliases.append(dict(self._aliases[-1]))
        self.generic_visit(node)
        self._aliases.pop()
        self._scope.pop()

    def _target(self, name: str, *, line: int) -> tuple[Symbol, float]:
        resolved_name = _resolve_alias(name, self._aliases[-1])
        if resolved_name == name:
            definition = self._resolve_definition(name)
            if definition is not None:
                return definition, 1.0
        return self._reference("reference", resolved_name, line), 0.75

    def _resolve_definition(self, name: str) -> Symbol | None:
        if name in self._definitions_by_qualified_name:
            return self._definitions_by_qualified_name[name]
        for scope in reversed(self._scope):
            candidate = f"{scope.qualified_name}.{name}"
            if candidate in self._definitions_by_qualified_name:
                return self._definitions_by_qualified_name[candidate]
        matches = self._definitions_by_name.get(name, [])
        return matches[0] if len(matches) == 1 else None

    def _reference(self, kind: str, qualified_name: str, line: int) -> Symbol:
        key = (kind, qualified_name, line)
        if key not in self._references:
            self._references[key] = create_symbol(
                kind=kind,
                name=qualified_name.rsplit(".", maxsplit=1)[-1],
                qualified_name=qualified_name,
                path=self._definitions.path,
                start_line=line,
                end_line=line,
            )
        return self._references[key]

    def _add_edge(
        self,
        source: Symbol,
        target: Symbol,
        kind: str,
        confidence: float,
    ) -> None:
        edge = create_relationship(
            source_id=source.id,
            target_id=target.id,
            kind=kind,
            confidence=confidence,
            source="python_ast",
        )
        self._edges[(source.id, target.id, kind)] = edge


def _module_name(path: str) -> str:
    candidate = PurePosixPath(path)
    parts = list(candidate.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or candidate.stem


def _expression_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expression_name(node.value)
        return f"{prefix}.{node.attr}" if prefix is not None else node.attr
    if isinstance(node, ast.Subscript):
        return _expression_name(node.value)
    return None


def _resolve_alias(name: str, aliases: dict[str, str]) -> str:
    first, separator, remainder = name.partition(".")
    resolved = aliases.get(first)
    if resolved is None:
        return name
    return f"{resolved}.{remainder}" if separator else resolved


def _symbol_sort_key(symbol: Symbol) -> tuple[int, int, str, str]:
    return (symbol.start_line, symbol.end_line, symbol.kind, symbol.qualified_name)


def _relationship_sort_key(
    relationship: Relationship,
) -> tuple[str, str, str, str]:
    return (
        relationship.source_id,
        relationship.kind,
        relationship.target_id,
        relationship.source,
    )
