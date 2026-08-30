from __future__ import annotations

from pathlib import Path
from typing import NoReturn, cast

from repo_dive.parsing.tree_sitter import LanguageLoader, TreeSitterParser
from repo_dive.scanner.models import FileRecord, ReadStatus

FIXTURE = Path(__file__).parents[2] / "fixtures" / "typescript_repo" / "sample.ts"


def source_record(path: str, language: str, text: str) -> FileRecord:
    return FileRecord(
        path=path,
        language=language,
        size_bytes=len(text.encode("utf-8")),
        content_hash="source-hash",
        encoding="utf-8",
        status=ReadStatus.READ,
        skip_reason=None,
    )


def test_tree_sitter_typescript_extracts_symbols_and_exact_chunks() -> None:
    text = FIXTURE.read_text(encoding="utf-8")

    result = TreeSitterParser("typescript").parse(
        source_record("src/sample.ts", "typescript", text),
        text,
    )

    definitions = {
        symbol.qualified_name: symbol
        for symbol in result.symbols
        if symbol.kind != "module"
    }
    assert set(definitions) == {
        "src.sample.Service",
        "src.sample.Service.run",
        "src.sample.helper",
    }
    assert definitions["src.sample.Service"].kind == "class"
    assert definitions["src.sample.Service.run"].kind == "method"
    assert definitions["src.sample.helper"].kind == "function"
    assert result.diagnostics == ()

    lines = text.splitlines(keepends=True)
    for chunk in result.chunks:
        assert chunk.text == "".join(lines[chunk.start_line - 1 : chunk.end_line])


def test_tree_sitter_derives_line_ranges_without_reading_point_fields() -> None:
    text = "const caf\u00e9 = 1;\nfunction hello() {\n  return caf\u00e9;\n}\n"
    source = text.encode("utf-8")
    function_start = source.index(b"function")
    name_start = source.index(b"hello")

    class ByteOnlyNode:
        def __init__(
            self,
            node_type: str,
            start_byte: int,
            end_byte: int,
            *,
            children: list[ByteOnlyNode] | None = None,
            name_node: ByteOnlyNode | None = None,
        ) -> None:
            self.type = node_type
            self.start_byte = start_byte
            self.end_byte = end_byte
            self.children = children or []
            self.has_error = False
            self._name_node = name_node

        @property
        def start_point(self) -> NoReturn:
            raise AssertionError("Tree-sitter Point fields must not be read")

        @property
        def end_point(self) -> NoReturn:
            raise AssertionError("Tree-sitter Point fields must not be read")

        def child_by_field_name(self, name: str) -> ByteOnlyNode | None:
            return self._name_node if name == "name" else None

    name_node = ByteOnlyNode("identifier", name_start, name_start + len(b"hello"))
    function_node = ByteOnlyNode(
        "function_declaration",
        function_start,
        len(source),
        name_node=name_node,
    )
    root_node = ByteOnlyNode("program", 0, len(source), children=[function_node])

    class ByteOnlyTree:
        def __init__(self, parsed_root: ByteOnlyNode) -> None:
            self.root_node = parsed_root

    class ByteOnlyParser:
        def parse(self, parsed_source: bytes) -> ByteOnlyTree:
            assert parsed_source == source
            return ByteOnlyTree(root_node)

    loader = cast(LanguageLoader, lambda language: ByteOnlyParser())
    result = TreeSitterParser("typescript", language_loader=loader).parse(
        source_record("src/sample.ts", "typescript", text),
        text,
    )

    function = next(symbol for symbol in result.symbols if symbol.kind == "function")
    assert (function.start_line, function.end_line) == (2, 4)
    assert result.chunks[0].text == "function hello() {\n  return caf\u00e9;\n}\n"


def test_missing_tree_sitter_grammar_falls_back_with_warning() -> None:
    text = "const answer = 42;\n"

    def unavailable(language: str) -> NoReturn:
        raise ImportError(f"missing {language}")

    result = TreeSitterParser(
        "typescript",
        language_loader=unavailable,
    ).parse(source_record("answer.ts", "typescript", text), text)

    assert len(result.chunks) == 1
    assert result.chunks[0].text == text
    assert result.symbols == ()
    assert result.diagnostics[0].code == "tree_sitter_unavailable"
    assert result.diagnostics[0].path == "answer.ts"
