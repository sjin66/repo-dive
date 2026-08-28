from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from repo_dive.errors import InternalOperationError
from repo_dive.indexing.bm25 import build_bm25_index, tokenize_code
from repo_dive.indexing.store import IndexStore
from repo_dive.parsing.models import Chunk, ParseResult, create_chunk
from repo_dive.scanner.models import FileRecord, ReadStatus, SourceFile


def corpus() -> tuple[Chunk, ...]:
    return (
        create_chunk(
            path="src/service.py",
            start_line=1,
            end_line=1,
            text="HTTPServer http_server",
        ),
        create_chunk(
            path="src/service.py",
            start_line=2,
            end_line=2,
            text="path/to/file.py HTTPServer",
        ),
        create_chunk(
            path="src/service.py",
            start_line=3,
            end_line=3,
            text="{}",
        ),
    )


def source_file(chunks: tuple[Chunk, ...]) -> SourceFile:
    text = "\n".join(chunk.text for chunk in chunks)
    return SourceFile(
        record=FileRecord(
            path="src/service.py",
            language="python",
            size_bytes=len(text.encode("utf-8")),
            content_hash="source-hash",
            encoding="utf-8",
            status=ReadStatus.READ,
            skip_reason=None,
        ),
        text=text,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "HTTPServer",
            ("HTTPServer", "httpserver", "HTTP", "http", "Server", "server"),
        ),
        ("http_server", ("http_server", "http", "server")),
        (
            "path/to/file.py",
            ("path/to/file.py", "path", "to", "file", "py"),
        ),
    ],
)
def test_tokenizer_preserves_whole_code_tokens_and_emits_parts(
    value: str,
    expected: tuple[str, ...],
) -> None:
    assert tokenize_code(value) == expected


def test_tokenizer_handles_unicode_and_ignores_symbol_only_text() -> None:
    assert tokenize_code("数据处理器 café_Éclair") == (
        "数据处理器",
        "café_Éclair",
        "café_éclair",
        "café",
        "Éclair",
        "éclair",
    )
    assert tokenize_code("{} [] () :: -> +=") == ()


def test_bm25_golden_corpus_has_stable_postings_and_statistics() -> None:
    chunks = corpus()

    index = build_bm25_index(chunks)

    assert build_bm25_index(reversed(chunks)) == index
    assert index.document_count == 3
    assert index.total_document_length == 20
    assert index.average_document_length == pytest.approx(20 / 3)
    assert index.parameters.k1 == 1.2
    assert index.parameters.b == 0.75
    assert index.parameters.tokenizer_version == "code-v1"
    assert dict(index.document_lengths) == {
        chunks[0].id: 9,
        chunks[1].id: 11,
        chunks[2].id: 0,
    }
    assert dict(index.document_frequencies) == {
        "HTTP": 2,
        "HTTPServer": 2,
        "Server": 2,
        "file": 1,
        "http": 2,
        "http_server": 1,
        "httpserver": 2,
        "path": 1,
        "path/to/file.py": 1,
        "py": 1,
        "server": 2,
        "to": 1,
    }
    assert {
        (posting.term, posting.chunk_id): posting.term_frequency
        for posting in index.postings
    } == {
        ("HTTP", chunks[0].id): 1,
        ("HTTP", chunks[1].id): 1,
        ("HTTPServer", chunks[0].id): 1,
        ("HTTPServer", chunks[1].id): 1,
        ("Server", chunks[0].id): 1,
        ("Server", chunks[1].id): 1,
        ("file", chunks[1].id): 1,
        ("http", chunks[0].id): 2,
        ("http", chunks[1].id): 1,
        ("http_server", chunks[0].id): 1,
        ("httpserver", chunks[0].id): 1,
        ("httpserver", chunks[1].id): 1,
        ("path", chunks[1].id): 1,
        ("path/to/file.py", chunks[1].id): 1,
        ("py", chunks[1].id): 1,
        ("server", chunks[0].id): 2,
        ("server", chunks[1].id): 1,
        ("to", chunks[1].id): 1,
    }


def test_store_round_trips_bm25_index_and_persists_golden_rows(
    tmp_path: Path,
) -> None:
    database = tmp_path / "index.sqlite3"
    chunks = corpus()
    index = build_bm25_index(chunks)

    with IndexStore.initialize(database) as store:
        store.replace_document(
            source_file(chunks),
            ParseResult(chunks=chunks),
        )
        store.replace_bm25_index(index)

    with IndexStore.open(database) as store:
        assert store.get_bm25_index() == index

    connection = sqlite3.connect(database)
    try:
        assert connection.execute("SELECT COUNT(*) FROM postings").fetchone() == (18,)
        assert connection.execute(
            "SELECT term, document_frequency FROM terms ORDER BY term"
        ).fetchall() == list(index.document_frequencies)
        assert dict(
            connection.execute(
                "SELECT id, token_count FROM chunks ORDER BY id"
            ).fetchall()
        ) == dict(index.document_lengths)
        assert dict(
            connection.execute(
                "SELECT key, value FROM stats WHERE key LIKE 'bm25.%' ORDER BY key"
            ).fetchall()
        ) == {
            "bm25.average_document_length": repr(index.average_document_length),
            "bm25.b": repr(index.parameters.b),
            "bm25.document_count": str(index.document_count),
            "bm25.k1": repr(index.parameters.k1),
            "bm25.tokenizer_version": index.parameters.tokenizer_version,
            "bm25.total_document_length": str(index.total_document_length),
        }
    finally:
        connection.close()


def test_store_rejects_bm25_document_for_missing_chunk(tmp_path: Path) -> None:
    chunks = corpus()
    database = tmp_path / "index.sqlite3"

    with (
        IndexStore.initialize(database) as store,
        pytest.raises(InternalOperationError) as exc_info,
    ):
        store.replace_bm25_index(build_bm25_index(chunks))

    assert exc_info.value.code == "index_integrity_error"


def test_replacing_document_invalidates_stale_bm25_index(tmp_path: Path) -> None:
    chunks = corpus()
    database = tmp_path / "index.sqlite3"

    with IndexStore.initialize(database) as store:
        store.replace_document(source_file(chunks), ParseResult(chunks=chunks))
        store.replace_bm25_index(build_bm25_index(chunks))

        store.replace_document(source_file(chunks), ParseResult(chunks=chunks))

        assert store.get_bm25_index() is None


def test_failed_bm25_rebuild_preserves_previous_index(tmp_path: Path) -> None:
    chunks = corpus()
    database = tmp_path / "index.sqlite3"
    index = build_bm25_index(chunks)
    missing_terms = replace(index, document_frequencies=())

    with IndexStore.initialize(database) as store:
        store.replace_document(source_file(chunks), ParseResult(chunks=chunks))
        store.replace_bm25_index(index)

        with pytest.raises(InternalOperationError) as exc_info:
            store.replace_bm25_index(missing_terms)

        assert exc_info.value.code == "index_integrity_error"
        assert store.get_bm25_index() == index


def test_store_rejects_semantically_corrupt_bm25_statistics(tmp_path: Path) -> None:
    chunks = corpus()
    database = tmp_path / "index.sqlite3"
    index = build_bm25_index(chunks)

    with IndexStore.initialize(database) as store:
        store.replace_document(source_file(chunks), ParseResult(chunks=chunks))
        store.replace_bm25_index(index)

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "UPDATE stats SET value = ? WHERE key = ?",
            ("999", "bm25.total_document_length"),
        )
        connection.commit()
    finally:
        connection.close()

    with (
        IndexStore.open(database) as store,
        pytest.raises(InternalOperationError) as exc_info,
    ):
        store.get_bm25_index()

    assert exc_info.value.code == "index_bm25_corrupt"
