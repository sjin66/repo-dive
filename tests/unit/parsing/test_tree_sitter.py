from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from repo_dive.parsing.tree_sitter import TreeSitterParser
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
