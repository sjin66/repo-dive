from __future__ import annotations

from pathlib import Path

from repo_dive.parsing.python_ast import PythonAstParser
from repo_dive.scanner.models import FileRecord, ReadStatus

FIXTURE = Path(__file__).parents[2] / "fixtures" / "python_repo" / "sample.py"


def python_record(path: str, text: str) -> FileRecord:
    return FileRecord(
        path=path,
        language="python",
        size_bytes=len(text.encode("utf-8")),
        content_hash="source-hash",
        encoding="utf-8",
        status=ReadStatus.READ,
        skip_reason=None,
    )


def test_python_ast_extracts_nested_symbols_and_exact_chunks() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    parser = PythonAstParser()

    result = parser.parse(python_record("src/sample.py", text), text)

    definitions = {
        symbol.qualified_name: symbol
        for symbol in result.symbols
        if symbol.kind not in {"import", "reference"}
    }
    assert set(definitions) == {
        "src.sample",
        "src.sample.Base",
        "src.sample.Service",
        "src.sample.Service.Nested",
        "src.sample.Service.Nested.execute",
        "src.sample.Service.run",
        "src.sample.helper",
        "src.sample.helper.inner",
    }
    assert definitions["src.sample.Service"].kind == "class"
    assert definitions["src.sample.Service"].start_line == 9
    assert definitions["src.sample.Service"].end_line == 20
    assert definitions["src.sample.Service.run"].kind == "method"
    assert definitions["src.sample.Service.run"].start_line == 11
    assert definitions["src.sample.Service.run"].end_line == 16
    assert definitions["src.sample.Service.Nested.execute"].kind == "method"
    assert definitions["src.sample.helper.inner"].kind == "function"

    lines = text.splitlines(keepends=True)
    assert result.chunks
    for chunk in result.chunks:
        assert chunk.symbol_id is not None
        assert chunk.text == "".join(lines[chunk.start_line - 1 : chunk.end_line])


def test_python_ast_extracts_contains_import_call_and_inheritance_edges() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    result = PythonAstParser().parse(python_record("src/sample.py", text), text)
    symbols = {symbol.id: symbol for symbol in result.symbols}
    edges = {
        (
            symbols[edge.source_id].qualified_name,
            symbols[edge.target_id].qualified_name,
            edge.kind,
        )
        for edge in result.relationships
    }

    assert ("src.sample", "src.sample.Service", "contains") in edges
    assert (
        "src.sample.Service",
        "src.sample.Service.run",
        "contains",
    ) in edges
    assert (
        "src.sample.Service.Nested",
        "src.sample.Service.Nested.execute",
        "contains",
    ) in edges
    assert ("src.sample", "os", "imports") in edges
    assert ("src.sample", "collections.defaultdict", "imports") in edges
    assert ("src.sample.Service", "src.sample.Base", "inherits") in edges
    assert ("src.sample.Service.run", "src.sample.helper", "calls") in edges
    assert (
        "src.sample.Service.Nested.execute",
        "os.getcwd",
        "calls",
    ) in edges
    assert (
        "src.sample.helper.inner",
        "collections.defaultdict",
        "calls",
    ) in edges
    assert ("src.sample.helper", "src.sample.helper.inner", "calls") in edges
    assert all(edge.source == "python_ast" for edge in result.relationships)
    assert all(edge.provenance == "python_ast" for edge in result.relationships)
    assert all(edge.path == "src/sample.py" for edge in result.relationships)
    assert all(0.0 < edge.confidence <= 1.0 for edge in result.relationships)

    contains_service = next(
        edge
        for edge in result.relationships
        if edge.kind == "contains"
        and symbols[edge.target_id].qualified_name == "src.sample.Service"
    )
    inheritance = next(edge for edge in result.relationships if edge.kind == "inherits")
    helper_call = next(
        edge
        for edge in result.relationships
        if edge.kind == "calls"
        and symbols[edge.target_id].qualified_name == "src.sample.helper"
    )
    assert (contains_service.start_line, contains_service.end_line) == (10, 20)
    assert (inheritance.start_line, inheritance.end_line) == (10, 10)
    assert (helper_call.start_line, helper_call.end_line) == (15, 15)


def test_python_ast_syntax_error_falls_back_with_diagnostic() -> None:
    text = "def broken(:\n    pass\n"

    result = PythonAstParser().parse(python_record("broken.py", text), text)

    assert result.symbols == ()
    assert result.relationships == ()
    assert len(result.chunks) == 1
    assert result.chunks[0].text == text
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "python_syntax_error"
    assert result.diagnostics[0].path == "broken.py"
    assert result.diagnostics[0].line == 1


def test_python_ast_output_is_deterministic() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    parser = PythonAstParser()
    record = python_record("src/sample.py", text)

    assert parser.parse(record, text) == parser.parse(record, text)


def test_python_ast_preserves_same_line_calls_and_import_alias_occurrences() -> None:
    text = (
        "import alpha, alpha\n"
        "def target():\n"
        "    pass\n"
        "def run():\n"
        "    target(); target()\n"
    )
    parser = PythonAstParser()
    record = python_record("src/repeated.py", text)

    first = parser.parse(record, text)
    second = parser.parse(record, text)
    symbols = {symbol.id: symbol for symbol in first.symbols}
    calls = tuple(edge for edge in first.relationships if edge.kind == "calls")
    imports = tuple(edge for edge in first.relationships if edge.kind == "imports")

    assert first.relationships == second.relationships
    assert len(calls) == 2
    assert len({edge.id for edge in calls}) == 2
    assert len({edge.occurrence_discriminator for edge in calls}) == 2
    assert {
        (symbols[edge.source_id].qualified_name, symbols[edge.target_id].qualified_name)
        for edge in calls
    } == {("src.repeated.run", "src.repeated.target")}
    assert {(edge.start_line, edge.end_line) for edge in calls} == {(5, 5)}
    assert len(imports) == 2
    assert len({edge.id for edge in imports}) == 2
    assert {(edge.start_line, edge.end_line) for edge in imports} == {(1, 1)}


def test_dotted_import_without_alias_preserves_bound_package_name() -> None:
    text = "import package.module\npackage.module.run()\n"
    result = PythonAstParser().parse(python_record("consumer.py", text), text)
    symbols = {symbol.id: symbol for symbol in result.symbols}
    call_targets = {
        symbols[edge.target_id].qualified_name
        for edge in result.relationships
        if edge.kind == "calls"
    }

    assert call_targets == {"package.module.run"}
