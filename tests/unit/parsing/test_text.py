from __future__ import annotations

from repo_dive.parsing.text import TextParser
from repo_dive.scanner.models import FileRecord, ReadStatus


def readable_record(path: str, language: str) -> FileRecord:
    return FileRecord(
        path=path,
        language=language,
        size_bytes=0,
        content_hash="source-hash",
        encoding="utf-8",
        status=ReadStatus.READ,
        skip_reason=None,
    )


def assert_chunk_matches_source(
    text: str, start_line: int, end_line: int, chunk: str
) -> None:
    lines = text.splitlines(keepends=True)
    assert chunk == "".join(lines[start_line - 1 : end_line])


def test_markdown_splits_on_headings_and_paragraphs() -> None:
    text = (
        "# Title\nIntroduction.\n\nSecond paragraph.\nContinued.\n\n## Details\nBody.\n"
    )
    parser = TextParser(window_lines=3, overlap_lines=1)

    result = parser.parse(readable_record("README.md", "markdown"), text)

    assert [
        (chunk.start_line, chunk.end_line, chunk.text) for chunk in result.chunks
    ] == [
        (1, 2, "# Title\nIntroduction.\n"),
        (4, 5, "Second paragraph.\nContinued.\n"),
        (7, 8, "## Details\nBody.\n"),
    ]
    for chunk in result.chunks:
        assert_chunk_matches_source(text, chunk.start_line, chunk.end_line, chunk.text)


def test_plain_text_uses_overlapping_line_windows() -> None:
    text = "one\ntwo\nthree\nfour\nfive\n"
    parser = TextParser(window_lines=3, overlap_lines=1)

    result = parser.parse(readable_record("notes.txt", "text"), text)

    assert [
        (chunk.start_line, chunk.end_line, chunk.text) for chunk in result.chunks
    ] == [
        (1, 3, "one\ntwo\nthree\n"),
        (3, 5, "three\nfour\nfive\n"),
    ]
    for chunk in result.chunks:
        assert_chunk_matches_source(text, chunk.start_line, chunk.end_line, chunk.text)


def test_empty_and_whitespace_only_text_produce_no_chunks() -> None:
    parser = TextParser(window_lines=3, overlap_lines=1)
    record = readable_record("notes.txt", "text")

    assert parser.parse(record, "").chunks == ()
    assert parser.parse(record, " \n\t\n").chunks == ()


def test_single_long_line_is_preserved_as_one_chunk() -> None:
    text = "x" * 10_000
    parser = TextParser(window_lines=3, overlap_lines=1)

    result = parser.parse(readable_record("generated.txt", "text"), text)

    assert len(result.chunks) == 1
    assert result.chunks[0].start_line == result.chunks[0].end_line == 1
    assert result.chunks[0].text == text


def test_text_parsing_is_deterministic() -> None:
    text = "alpha\nbeta\ngamma\ndelta\n"
    parser = TextParser(window_lines=2, overlap_lines=1)
    record = readable_record("notes.txt", "text")

    first = parser.parse(record, text)
    second = parser.parse(record, text)

    assert first == second


def test_parser_configuration_requires_progress() -> None:
    try:
        TextParser(window_lines=2, overlap_lines=2)
    except ValueError as error:
        assert "overlap_lines" in str(error)
    else:
        raise AssertionError("Expected invalid overlap to be rejected")
