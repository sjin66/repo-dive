from __future__ import annotations

from repo_dive.parsing.models import ParseResult, create_relationship
from repo_dive.parsing.pipeline import ParsingPipeline
from repo_dive.parsing.registry import ParserRegistry
from repo_dive.scanner.models import (
    FileRecord,
    ReadStatus,
    SkipReason,
    SourceFile,
)


def source_file(
    path: str,
    language: str,
    text: str | None,
    *,
    status: ReadStatus = ReadStatus.READ,
    skip_reason: SkipReason | None = None,
) -> SourceFile:
    return SourceFile(
        record=FileRecord(
            path=path,
            language=language,
            size_bytes=len(text.encode("utf-8")) if text is not None else 0,
            content_hash="source-hash" if text is not None else None,
            encoding="utf-8" if text is not None else None,
            status=status,
            skip_reason=skip_reason,
        ),
        text=text,
    )


def test_pipeline_selects_python_ast_by_language() -> None:
    source = source_file("service.py", "python", "def run():\n    return 1\n")

    result = ParsingPipeline().parse(source)

    assert any(symbol.qualified_name == "service.run" for symbol in result.symbols)


def test_pipeline_can_recover_parser_selection_from_path() -> None:
    source = source_file("service.py", "unknown", "def run():\n    return 1\n")

    result = ParsingPipeline().parse(source)

    assert any(symbol.qualified_name == "service.run" for symbol in result.symbols)


def test_pipeline_uses_text_fallback_for_unknown_language() -> None:
    source = source_file("notes.custom", "unknown", "alpha\nbeta\n")

    result = ParsingPipeline().parse(source)

    assert len(result.chunks) == 1
    assert result.chunks[0].text == "alpha\nbeta\n"


def test_pipeline_splits_oversized_chunks_on_exact_line_boundaries() -> None:
    text = "one\ntwo\nthree\nfour\nfive\n"
    source = source_file("notes.txt", "text", text)

    result = ParsingPipeline(max_chunk_lines=2).parse(source)

    assert [
        (chunk.start_line, chunk.end_line, chunk.text) for chunk in result.chunks
    ] == [
        (1, 2, "one\ntwo\n"),
        (3, 4, "three\nfour\n"),
        (5, 5, "five\n"),
    ]


def test_pipeline_reports_skipped_source_without_parsing() -> None:
    source = source_file(
        "binary.dat",
        "unknown",
        None,
        status=ReadStatus.SKIPPED,
        skip_reason=SkipReason.BINARY,
    )

    result = ParsingPipeline().parse(source)

    assert result.chunks == ()
    assert result.diagnostics[0].code == "source_not_readable"


def test_pipeline_output_is_deterministic() -> None:
    source = source_file("notes.txt", "text", "one\ntwo\nthree\n")
    pipeline = ParsingPipeline(max_chunk_lines=2)

    assert pipeline.parse(source) == pipeline.parse(source)


def test_pipeline_normalizes_relationships_by_occurrence_identity() -> None:
    first = create_relationship(
        source_id="symbol:source",
        target_id="symbol:target",
        kind="calls",
        confidence=1.0,
        provenance="fixture",
        path="service.py",
        start_line=3,
        end_line=3,
        occurrence_discriminator=(4, 12, 0),
    )
    second = create_relationship(
        source_id="symbol:source",
        target_id="symbol:target",
        kind="calls",
        confidence=1.0,
        provenance="fixture",
        path="service.py",
        start_line=3,
        end_line=3,
        occurrence_discriminator=(15, 23, 0),
    )

    class Parser:
        def parse(self, file: FileRecord, text: str) -> ParseResult:
            return ParseResult(relationships=(second, first, first))

    class Registry(ParserRegistry):
        def __init__(self) -> None:
            pass

        def parser_for(self, file: FileRecord) -> Parser:
            return Parser()

    result = ParsingPipeline(registry=Registry()).parse(
        source_file("service.py", "python", "target(); target()\n")
    )

    assert result.relationships == (first, second)
