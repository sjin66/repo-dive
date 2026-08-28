from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from repo_dive.parsing.models import (
    ParserAdapter,
    ParseResult,
    create_chunk,
    create_relationship,
    create_symbol,
)
from repo_dive.scanner.models import FileRecord, ReadStatus


def readable_record(path: str = "src/main.py") -> FileRecord:
    return FileRecord(
        path=path,
        language="python",
        size_bytes=5,
        content_hash="source-hash",
        encoding="utf-8",
        status=ReadStatus.READ,
        skip_reason=None,
    )


def test_chunk_identity_and_content_hash_are_stable() -> None:
    first = create_chunk(
        path="src/main.py",
        start_line=2,
        end_line=3,
        text="value = 1\nreturn value\n",
    )
    second = create_chunk(
        path="src/main.py",
        start_line=2,
        end_line=3,
        text="value = 1\nreturn value\n",
    )
    changed = create_chunk(
        path="src/main.py",
        start_line=2,
        end_line=3,
        text="value = 2\nreturn value\n",
    )

    assert first == second
    assert first.id.startswith("chunk:")
    assert len(first.content_hash) == 64
    assert first.id != changed.id
    assert first.content_hash != changed.content_hash


def test_symbol_and_relationship_identity_are_stable() -> None:
    symbol = create_symbol(
        kind="function",
        name="run",
        qualified_name="service.run",
        path="src/service.py",
        start_line=4,
        end_line=8,
    )
    same_symbol = create_symbol(
        kind="function",
        name="run",
        qualified_name="service.run",
        path="src/service.py",
        start_line=4,
        end_line=8,
    )
    relationship = create_relationship(
        source_id=symbol.id,
        target_id="symbol:target",
        kind="calls",
        confidence=0.75,
        source="python_ast",
    )

    assert symbol == same_symbol
    assert symbol.id.startswith("symbol:")
    assert relationship.source_id == symbol.id
    assert relationship.confidence == 0.75
    assert relationship.source == "python_ast"


@pytest.mark.parametrize(
    ("start_line", "end_line"),
    [(0, 1), (2, 1)],
)
def test_chunk_rejects_invalid_line_ranges(start_line: int, end_line: int) -> None:
    with pytest.raises(ValueError, match="line range"):
        create_chunk(
            path="README.md",
            start_line=start_line,
            end_line=end_line,
            text="text\n",
        )


def test_relationship_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        create_relationship(
            source_id="source",
            target_id="target",
            kind="calls",
            confidence=1.1,
            source="test",
        )


def test_models_are_frozen() -> None:
    chunk = create_chunk(
        path="README.md",
        start_line=1,
        end_line=1,
        text="# Title\n",
    )

    with pytest.raises(FrozenInstanceError):
        chunk.text = "changed"  # type: ignore[misc]


def test_parser_protocol_only_requires_record_and_text() -> None:
    class Parser:
        def parse(self, file: FileRecord, text: str) -> ParseResult:
            return ParseResult()

    parser: ParserAdapter = Parser()

    assert parser.parse(readable_record(), "pass\n") == ParseResult()
