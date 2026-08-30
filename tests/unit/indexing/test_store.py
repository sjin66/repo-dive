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
        provenance="python_ast",
        path="src/service.py",
        start_line=1,
        end_line=2,
        occurrence_discriminator=(0, 27, 0),
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
                provenance="test",
                path="src/service.py",
                start_line=2,
                end_line=2,
                occurrence_discriminator=(4, 12, 0),
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
        connection.execute(
            "INSERT INTO terms (term, document_frequency) VALUES (?, ?)",
            ("run", 1),
        )

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


def test_store_preserves_each_relationship_occurrence(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    source = source_file()
    parsed = parse_result()
    first = parsed.relationships[0]
    repeated = create_relationship(
        source_id=first.source_id,
        target_id=first.target_id,
        kind=first.kind,
        confidence=first.confidence,
        provenance=first.provenance,
        path=first.path,
        start_line=first.start_line,
        end_line=first.end_line,
        occurrence_discriminator=(12, 39, 0),
    )
    occurrences = ParseResult(
        chunks=parsed.chunks,
        symbols=parsed.symbols,
        relationships=(first, repeated),
    )

    with IndexStore.initialize(database) as store:
        store.replace_document(source, occurrences)
        assert store.get_parse_result("src/service.py") == occurrences
        assert store.query_relationship_occurrences(
            (first.source_id,),
            direction="outgoing",
            edge_kinds=("contains",),
            limit=10,
        ) == (first, repeated)


def test_store_rejects_relationship_from_a_different_path(tmp_path: Path) -> None:
    parsed = parse_result()
    relationship = parsed.relationships[0]
    mismatched = create_relationship(
        source_id=relationship.source_id,
        target_id=relationship.target_id,
        kind=relationship.kind,
        confidence=relationship.confidence,
        provenance=relationship.provenance,
        path="src/other.py",
        start_line=relationship.start_line,
        end_line=relationship.end_line,
        occurrence_discriminator=relationship.occurrence_discriminator,
    )

    with (
        IndexStore.initialize(tmp_path / "index.sqlite3") as store,
        pytest.raises(InternalOperationError) as exc_info,
    ):
        store.replace_document(
            source_file(),
            ParseResult(symbols=parsed.symbols, relationships=(mismatched,)),
        )

    assert exc_info.value.code == "index_document_path_mismatch"


def test_store_rejects_duplicate_relationship_identity(tmp_path: Path) -> None:
    parsed = parse_result()
    relationship = parsed.relationships[0]
    duplicated = ParseResult(
        chunks=parsed.chunks,
        symbols=parsed.symbols,
        relationships=(relationship, relationship),
    )

    with (
        IndexStore.initialize(tmp_path / "index.sqlite3") as store,
        pytest.raises(InternalOperationError) as exc_info,
    ):
        store.replace_document(source_file(), duplicated)

    assert exc_info.value.code == "index_integrity_error"


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


def test_readonly_store_rejects_mutation_and_reads_all_chunks(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    parsed = parse_result()
    with IndexStore.initialize(database) as store:
        store.replace_document(source_file(), parsed)

    with IndexStore.open_readonly(database) as store:
        assert store.get_chunks() == parsed.chunks
        with pytest.raises(InternalOperationError) as exc_info:
            store.replace_document(source_file(), ParseResult())

    assert exc_info.value.code == "index_read_only"
