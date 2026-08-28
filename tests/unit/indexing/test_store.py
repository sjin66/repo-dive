from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION, IndexStore
from repo_dive.parsing.models import (
    ParseResult,
    create_chunk,
    create_relationship,
    create_symbol,
)
from repo_dive.scanner.models import FileRecord, ReadStatus, SourceFile

EXPECTED_TABLES = {
    "chunks",
    "files",
    "postings",
    "relationships",
    "stats",
    "symbols",
    "terms",
    "vectors",
}


def source_file() -> SourceFile:
    text = "def run():\n    return 1\n"
    return SourceFile(
        record=FileRecord(
            path="src/service.py",
            language="python",
            size_bytes=len(text.encode("utf-8")),
            content_hash="file-hash",
            encoding="utf-8",
            status=ReadStatus.READ,
            skip_reason=None,
        ),
        text=text,
    )


def parse_result() -> ParseResult:
    module = create_symbol(
        kind="module",
        name="service",
        qualified_name="src.service",
        path="src/service.py",
        start_line=1,
        end_line=2,
    )
    function = create_symbol(
        kind="function",
        name="run",
        qualified_name="src.service.run",
        path="src/service.py",
        start_line=1,
        end_line=2,
    )
    chunk = create_chunk(
        path="src/service.py",
        start_line=1,
        end_line=2,
        text="def run():\n    return 1\n",
        symbol_id=function.id,
    )
    relationship = create_relationship(
        source_id=module.id,
        target_id=function.id,
        kind="contains",
        confidence=1.0,
        source="python_ast",
    )
    return ParseResult(
        chunks=(chunk,),
        symbols=(module, function),
        relationships=(relationship,),
    )


def test_initialize_creates_versioned_schema_and_required_tables(
    tmp_path: Path,
) -> None:
    database = tmp_path / "index.sqlite3"

    with IndexStore.initialize(database) as store:
        assert store.schema_version == INDEX_SCHEMA_VERSION
        assert store.table_names() == EXPECTED_TABLES
        assert store.foreign_key_violations() == ()
        assert store.integrity_check() == ("ok",)


def test_store_round_trips_typed_file_and_parse_result(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    source = source_file()
    parsed = parse_result()

    with IndexStore.initialize(database) as store:
        store.replace_document(source, parsed)

    with IndexStore.open(database) as store:
        assert store.get_file("src/service.py") == source.record
        assert store.get_parse_result("src/service.py") == parsed


def test_invalid_relationship_preserves_existing_document(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    parsed = parse_result()
    invalid = ParseResult(
        chunks=parsed.chunks,
        symbols=parsed.symbols,
        relationships=(
            create_relationship(
                source_id=parsed.symbols[0].id,
                target_id="symbol:missing",
                kind="calls",
                confidence=0.5,
                source="test",
            ),
        ),
    )

    with IndexStore.initialize(database) as store:
        store.replace_document(source_file(), parsed)

        with pytest.raises(InternalOperationError) as exc_info:
            store.replace_document(source_file(), invalid)

        assert exc_info.value.code == "index_integrity_error"
        assert store.get_file("src/service.py") == source_file().record
        assert store.get_parse_result("src/service.py") == parsed
        assert store.foreign_key_violations() == ()


def test_schema_rejects_posting_for_missing_chunk(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    with IndexStore.initialize(database):
        pass

    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("INSERT INTO terms (term) VALUES (?)", ("run",))

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO postings (term_id, chunk_id, term_frequency) "
                "VALUES (?, ?, ?)",
                (1, "chunk:missing", 1),
            )
    finally:
        connection.close()


def test_store_rejects_parse_objects_from_a_different_path(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    parsed = parse_result()
    mismatched = ParseResult(
        chunks=(
            create_chunk(
                path="src/other.py",
                start_line=1,
                end_line=1,
                text="pass\n",
            ),
        ),
        symbols=parsed.symbols,
    )

    with IndexStore.initialize(database) as store:
        with pytest.raises(InternalOperationError) as exc_info:
            store.replace_document(source_file(), mismatched)

        assert exc_info.value.code == "index_document_path_mismatch"
        assert store.get_file("src/service.py") is None


def test_open_rejects_unknown_schema_version(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA user_version = 99")
    connection.close()

    with pytest.raises(RepositoryError) as exc_info:
        IndexStore.open(database)

    assert exc_info.value.code == "index_schema_version_unsupported"
    assert exc_info.value.details == {"actual": 99, "expected": INDEX_SCHEMA_VERSION}


def test_open_rejects_missing_database(tmp_path: Path) -> None:
    with pytest.raises(RepositoryError) as exc_info:
        IndexStore.open(tmp_path / "missing.sqlite3")

    assert exc_info.value.code == "index_not_found"
