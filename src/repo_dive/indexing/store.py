"""Typed SQLite storage for the private repository index."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from math import isclose
from pathlib import Path
from types import TracebackType
from typing import Literal, cast

from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.indexing.bm25 import BM25Index, BM25Parameters, Posting
from repo_dive.parsing.models import Chunk, ParseResult, Relationship, Symbol
from repo_dive.scanner.models import (
    FileRecord,
    ReadStatus,
    SkipReason,
    SourceFile,
)

INDEX_SCHEMA_VERSION = 3

_BM25_STAT_KEYS = {
    "average_document_length": "bm25.average_document_length",
    "b": "bm25.b",
    "document_count": "bm25.document_count",
    "k1": "bm25.k1",
    "tokenizer_version": "bm25.tokenizer_version",
    "total_document_length": "bm25.total_document_length",
}


class IndexStore:
    """The only supported connection boundary for the private SQLite index."""

    def __init__(
        self,
        database: Path,
        connection: sqlite3.Connection,
        *,
        read_only: bool = False,
    ) -> None:
        self.database = database
        self._connection = connection
        self._read_only = read_only
        self._closed = False

    @classmethod
    def initialize(cls, database: str | Path) -> IndexStore:
        """Create a new index, or validate an existing compatible index."""
        path = Path(database)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = _connect(path)
        store = cls(path, connection)
        try:
            version = store.schema_version
            if version == 0 and not store.table_names():
                schema = (
                    resources.files("repo_dive.indexing")
                    .joinpath("schema.sql")
                    .read_text(encoding="utf-8")
                )
                connection.executescript(schema)
            store._validate_schema_version()
        except Exception:
            store.close()
            raise
        return store

    @classmethod
    def open(cls, database: str | Path) -> IndexStore:
        """Open an existing index only when its Schema is supported."""
        path = Path(database)
        if not path.is_file():
            raise RepositoryError(
                "index_not_found",
                "Repository index does not exist.",
                details={"path": str(path)},
            )
        connection = _connect(path)
        store = cls(path, connection)
        try:
            store._validate_schema_version()
        except Exception:
            store.close()
            raise
        return store

    @classmethod
    def open_readonly(cls, database: str | Path) -> IndexStore:
        """Open an existing compatible index with SQLite writes disabled."""
        path = Path(database)
        if not path.is_file():
            raise RepositoryError(
                "index_not_found",
                "Repository index does not exist.",
                details={"path": str(path)},
            )
        connection = _connect(path, read_only=True)
        store = cls(path, connection, read_only=True)
        try:
            store._validate_schema_version()
        except Exception:
            store.close()
            raise
        return store

    def __enter__(self) -> IndexStore:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def schema_version(self) -> int:
        """Return SQLite's application-controlled Schema version."""
        self._ensure_open()
        row = self._connection.execute("PRAGMA user_version").fetchone()
        return int(row[0])

    def close(self) -> None:
        """Close the underlying connection; repeated calls are harmless."""
        if not self._closed:
            self._connection.close()
            self._closed = True

    def table_names(self) -> set[str]:
        """Return application table names, excluding SQLite internals."""
        self._ensure_open()
        rows = self._connection.execute(
            "SELECT name FROM sqlite_schema "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {cast(str, row[0]) for row in rows}

    def replace_document(self, source: SourceFile, parsed: ParseResult) -> None:
        """Atomically replace one file and all of its parsed index records."""
        self._ensure_open()
        self._ensure_writable()
        _validate_document_path(source.record.path, parsed)
        try:
            with self._transaction():
                self._clear_bm25_index()
                self._connection.execute(
                    "DELETE FROM files WHERE path = ?", (source.record.path,)
                )
                self._insert_file(source.record)
                self._insert_symbols(source.record.path, parsed.symbols)
                self._insert_chunks(source.record.path, parsed.chunks)
                self._insert_relationships(source.record.path, parsed.relationships)
        except sqlite3.IntegrityError as error:
            raise InternalOperationError(
                "index_integrity_error",
                "Index records violate the internal integrity contract.",
            ) from error
        except sqlite3.Error as error:
            raise InternalOperationError(
                "index_write_failed",
                "Could not update the repository index.",
            ) from error

    def replace_bm25_index(self, index: BM25Index) -> None:
        """Atomically replace all lexical postings and corpus statistics."""
        self._ensure_open()
        self._ensure_writable()
        if not _is_valid_bm25_index(index):
            raise InternalOperationError(
                "index_integrity_error",
                "BM25 records violate the internal integrity contract.",
            )
        try:
            with self._transaction():
                expected_chunk_ids = {
                    cast(str, row[0])
                    for row in self._connection.execute("SELECT id FROM chunks")
                }
                actual_chunk_ids = {chunk_id for chunk_id, _ in index.document_lengths}
                if actual_chunk_ids != expected_chunk_ids:
                    raise InternalOperationError(
                        "index_integrity_error",
                        "BM25 documents do not match the indexed Chunks.",
                    )

                self._clear_bm25_index()
                for chunk_id, token_count in index.document_lengths:
                    self._connection.execute(
                        "UPDATE chunks SET token_count = ? WHERE id = ?",
                        (token_count, chunk_id),
                    )

                term_ids = {
                    term: term_id
                    for term_id, (term, _) in enumerate(
                        index.document_frequencies,
                        start=1,
                    )
                }
                self._connection.executemany(
                    "INSERT INTO terms (id, term, document_frequency) VALUES (?, ?, ?)",
                    (
                        (term_ids[term], term, document_frequency)
                        for term, document_frequency in index.document_frequencies
                    ),
                )
                self._connection.executemany(
                    "INSERT INTO postings (term_id, chunk_id, term_frequency) "
                    "VALUES (?, ?, ?)",
                    (
                        (
                            term_ids[posting.term],
                            posting.chunk_id,
                            posting.term_frequency,
                        )
                        for posting in index.postings
                    ),
                )
                self._connection.executemany(
                    "INSERT INTO stats (key, value) VALUES (?, ?)",
                    _bm25_stats(index),
                )
        except InternalOperationError:
            raise
        except (KeyError, sqlite3.IntegrityError) as error:
            raise InternalOperationError(
                "index_integrity_error",
                "BM25 records violate the internal integrity contract.",
            ) from error
        except sqlite3.Error as error:
            raise InternalOperationError(
                "index_write_failed",
                "Could not update the BM25 index.",
            ) from error

    def get_bm25_index(self) -> BM25Index | None:
        """Read the complete persisted BM25 corpus, or None before a build."""
        self._ensure_open()
        rows = self._connection.execute(
            "SELECT key, value FROM stats WHERE key LIKE 'bm25.%'"
        ).fetchall()
        if not rows:
            return None

        stats = {cast(str, row[0]): cast(str, row[1]) for row in rows}
        try:
            parameters = BM25Parameters(
                k1=float(stats[_BM25_STAT_KEYS["k1"]]),
                b=float(stats[_BM25_STAT_KEYS["b"]]),
                tokenizer_version=stats[_BM25_STAT_KEYS["tokenizer_version"]],
            )
            document_count = int(stats[_BM25_STAT_KEYS["document_count"]])
            total_document_length = int(stats[_BM25_STAT_KEYS["total_document_length"]])
            average_document_length = float(
                stats[_BM25_STAT_KEYS["average_document_length"]]
            )
        except (KeyError, ValueError) as error:
            raise InternalOperationError(
                "index_bm25_corrupt",
                "BM25 statistics are incomplete or invalid.",
            ) from error

        document_lengths = tuple(
            (cast(str, row[0]), cast(int, row[1]))
            for row in self._connection.execute(
                "SELECT id, token_count FROM chunks ORDER BY id"
            )
        )
        document_frequencies = tuple(
            (cast(str, row[0]), cast(int, row[1]))
            for row in self._connection.execute(
                "SELECT term, document_frequency FROM terms ORDER BY term"
            )
        )
        postings = tuple(
            Posting(
                term=cast(str, row[0]),
                chunk_id=cast(str, row[1]),
                term_frequency=cast(int, row[2]),
            )
            for row in self._connection.execute(
                "SELECT terms.term, postings.chunk_id, postings.term_frequency "
                "FROM postings JOIN terms ON terms.id = postings.term_id "
                "ORDER BY terms.term, postings.chunk_id"
            )
        )
        index = BM25Index(
            parameters=parameters,
            document_count=document_count,
            total_document_length=total_document_length,
            average_document_length=average_document_length,
            document_lengths=document_lengths,
            document_frequencies=document_frequencies,
            postings=postings,
        )
        if not _is_valid_bm25_index(index):
            raise InternalOperationError(
                "index_bm25_corrupt",
                "BM25 records are internally inconsistent.",
            )
        return index

    def query_symbols(
        self,
        query: str,
        *,
        path: str | None,
        max_results: int,
    ) -> tuple[Symbol, ...]:
        """Find exact then case-folded symbol matches with a stable order."""
        self._ensure_open()
        if not query or max_results <= 0:
            raise ValueError("symbol query and max_results must be positive")

        normalized = query.casefold()
        path_clause = " AND file_path = ?" if path is not None else ""
        parameters: list[str | int] = [
            query,
            query,
            normalized,
            normalized,
        ]
        if path is not None:
            parameters.append(path)
        parameters.extend((query, query, normalized, max_results))
        rows = self._connection.execute(
            "SELECT id, kind, name, qualified_name, file_path, start_line, end_line "
            "FROM symbols WHERE "
            "(name = ? OR qualified_name = ? OR name_normalized = ? "
            "OR qualified_name_normalized = ?)"
            f"{path_clause} "
            "ORDER BY CASE "
            "WHEN qualified_name = ? THEN 0 "
            "WHEN name = ? THEN 1 "
            "WHEN qualified_name_normalized = ? THEN 2 "
            "ELSE 3 END, file_path, start_line, end_line, id LIMIT ?",
            parameters,
        )
        return tuple(_symbol_from_row(row) for row in rows)

    def get_symbols_by_id(self, symbol_ids: tuple[str, ...]) -> tuple[Symbol, ...]:
        """Read a bounded caller-supplied set of Symbols by identity."""
        self._ensure_open()
        if not symbol_ids:
            return ()
        placeholders = ", ".join("?" for _ in symbol_ids)
        rows = self._connection.execute(
            "SELECT id, kind, name, qualified_name, file_path, start_line, end_line "
            f"FROM symbols WHERE id IN ({placeholders}) ORDER BY id",
            symbol_ids,
        )
        return tuple(_symbol_from_row(row) for row in rows)

    def query_relationships(
        self,
        symbol_ids: tuple[str, ...],
        *,
        direction: Literal["outgoing", "incoming", "both"],
        edge_kinds: tuple[str, ...] | None,
        limit: int,
        min_confidence: float = 0.0,
    ) -> tuple[Relationship, ...]:
        """Read a stable, bounded relationship frontier for graph traversal."""
        self._ensure_open()
        if not symbol_ids:
            return ()
        if (
            direction not in {"outgoing", "incoming", "both"}
            or limit <= 0
            or not 0.0 <= min_confidence <= 1.0
        ):
            raise ValueError("relationship query parameters must be valid")

        placeholders = ", ".join("?" for _ in symbol_ids)
        parameters: list[str | int | float] = []
        if direction == "outgoing":
            frontier_clause = f"source_id IN ({placeholders})"
            parameters.extend(symbol_ids)
        elif direction == "incoming":
            frontier_clause = f"target_id IN ({placeholders})"
            parameters.extend(symbol_ids)
        else:
            frontier_clause = (
                f"(source_id IN ({placeholders}) OR target_id IN ({placeholders}))"
            )
            parameters.extend(symbol_ids)
            parameters.extend(symbol_ids)

        kind_clause = ""
        if edge_kinds is not None:
            if not edge_kinds:
                return ()
            kind_placeholders = ", ".join("?" for _ in edge_kinds)
            kind_clause = f" AND kind IN ({kind_placeholders})"
            parameters.extend(edge_kinds)
        parameters.extend((min_confidence, limit))
        rows = self._connection.execute(
            "SELECT source_id, target_id, kind, confidence, source "
            f"FROM relationships WHERE {frontier_clause}{kind_clause} "
            "AND confidence >= ? "
            "ORDER BY source_id, target_id, kind, source LIMIT ?",
            parameters,
        )
        return tuple(_relationship_from_row(row) for row in rows)

    def get_file(self, path: str) -> FileRecord | None:
        """Read one typed file record by repository-relative path."""
        self._ensure_open()
        row = self._connection.execute(
            "SELECT path, language, size_bytes, content_hash, encoding, status, "
            "skip_reason FROM files WHERE path = ?",
            (path,),
        ).fetchone()
        if row is None:
            return None
        skip_reason_value = cast(str | None, row[6])
        return FileRecord(
            path=cast(str, row[0]),
            language=cast(str, row[1]),
            size_bytes=cast(int, row[2]),
            content_hash=cast(str | None, row[3]),
            encoding=cast(str | None, row[4]),
            status=ReadStatus(cast(str, row[5])),
            skip_reason=(
                SkipReason(skip_reason_value) if skip_reason_value is not None else None
            ),
        )

    def get_parse_result(self, path: str) -> ParseResult:
        """Read stored parsing objects for one repository-relative file."""
        self._ensure_open()
        symbols = tuple(
            _symbol_from_row(row)
            for row in self._connection.execute(
                "SELECT id, kind, name, qualified_name, file_path, start_line, "
                "end_line FROM symbols WHERE file_path = ? ORDER BY ordinal",
                (path,),
            )
        )
        chunks = tuple(
            _chunk_from_row(row)
            for row in self._connection.execute(
                "SELECT id, file_path, start_line, end_line, text, symbol_id, "
                "content_hash FROM chunks WHERE file_path = ? ORDER BY ordinal",
                (path,),
            )
        )
        relationships = tuple(
            _relationship_from_row(row)
            for row in self._connection.execute(
                "SELECT source_id, target_id, kind, confidence, source "
                "FROM relationships WHERE file_path = ? ORDER BY ordinal",
                (path,),
            )
        )
        return ParseResult(
            chunks=chunks,
            symbols=symbols,
            relationships=relationships,
        )

    def get_chunks(self) -> tuple[Chunk, ...]:
        """Read every Chunk once in stable repository and source order."""
        self._ensure_open()
        rows = self._connection.execute(
            "SELECT id, file_path, start_line, end_line, text, symbol_id, "
            "content_hash FROM chunks ORDER BY file_path, ordinal"
        )
        return tuple(_chunk_from_row(row) for row in rows)

    def foreign_key_violations(
        self,
    ) -> tuple[tuple[str, int | None, str, int], ...]:
        """Return every foreign-key violation reported by SQLite."""
        self._ensure_open()
        return tuple(
            (
                cast(str, row[0]),
                cast(int | None, row[1]),
                cast(str, row[2]),
                cast(int, row[3]),
            )
            for row in self._connection.execute("PRAGMA foreign_key_check")
        )

    def integrity_check(self) -> tuple[str, ...]:
        """Return SQLite's structural integrity results."""
        self._ensure_open()
        return tuple(
            cast(str, row[0])
            for row in self._connection.execute("PRAGMA integrity_check")
        )

    def _validate_schema_version(self) -> None:
        actual = self.schema_version
        if actual != INDEX_SCHEMA_VERSION:
            raise RepositoryError(
                "index_schema_version_unsupported",
                "Repository index Schema version is not supported.",
                details={"actual": actual, "expected": INDEX_SCHEMA_VERSION},
            )

    def _ensure_open(self) -> None:
        if self._closed:
            raise InternalOperationError(
                "index_store_closed",
                "Repository index Store is already closed.",
            )

    def _ensure_writable(self) -> None:
        if self._read_only:
            raise InternalOperationError(
                "index_read_only",
                "Repository index is open for reading only.",
            )

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()

    def _insert_file(self, record: FileRecord) -> None:
        self._connection.execute(
            "INSERT INTO files "
            "(path, language, size_bytes, content_hash, encoding, status, skip_reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record.path,
                record.language,
                record.size_bytes,
                record.content_hash,
                record.encoding,
                record.status.value,
                record.skip_reason.value if record.skip_reason is not None else None,
            ),
        )

    def _insert_symbols(self, file_path: str, symbols: tuple[Symbol, ...]) -> None:
        self._connection.executemany(
            "INSERT INTO symbols "
            "(id, file_path, ordinal, kind, name, name_normalized, "
            "qualified_name, qualified_name_normalized, start_line, end_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    symbol.id,
                    file_path,
                    ordinal,
                    symbol.kind,
                    symbol.name,
                    symbol.name.casefold(),
                    symbol.qualified_name,
                    symbol.qualified_name.casefold(),
                    symbol.start_line,
                    symbol.end_line,
                )
                for ordinal, symbol in enumerate(symbols)
            ),
        )

    def _insert_chunks(self, file_path: str, chunks: tuple[Chunk, ...]) -> None:
        self._connection.executemany(
            "INSERT INTO chunks "
            "(id, file_path, ordinal, start_line, end_line, text, symbol_id, "
            "content_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    chunk.id,
                    file_path,
                    ordinal,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.text,
                    chunk.symbol_id,
                    chunk.content_hash,
                )
                for ordinal, chunk in enumerate(chunks)
            ),
        )

    def _insert_relationships(
        self, file_path: str, relationships: tuple[Relationship, ...]
    ) -> None:
        self._connection.executemany(
            "INSERT INTO relationships "
            "(file_path, ordinal, source_id, target_id, kind, confidence, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    file_path,
                    ordinal,
                    relationship.source_id,
                    relationship.target_id,
                    relationship.kind,
                    relationship.confidence,
                    relationship.source,
                )
                for ordinal, relationship in enumerate(relationships)
            ),
        )

    def _clear_bm25_index(self) -> None:
        self._connection.execute("DELETE FROM postings")
        self._connection.execute("DELETE FROM terms")
        self._connection.execute("DELETE FROM stats WHERE key LIKE 'bm25.%'")
        self._connection.execute("UPDATE chunks SET token_count = 0")


def _connect(path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    try:
        target: str | Path = path
        if read_only:
            target = f"{path.resolve(strict=True).as_uri()}?mode=ro"
        connection = sqlite3.connect(
            target,
            isolation_level=None,
            uri=read_only,
        )
        if read_only:
            connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as error:
        raise RepositoryError(
            "index_unavailable",
            "Repository index is not available.",
            details={"path": str(path)},
        ) from error


def _validate_document_path(file_path: str, parsed: ParseResult) -> None:
    mismatched_paths = sorted(
        {symbol.path for symbol in parsed.symbols if symbol.path != file_path}
        | {chunk.path for chunk in parsed.chunks if chunk.path != file_path}
    )
    if mismatched_paths:
        raise InternalOperationError(
            "index_document_path_mismatch",
            "Parsed index records do not belong to the source file.",
            details={
                "path": file_path,
                "mismatch_count": len(mismatched_paths),
            },
        )


def _bm25_stats(index: BM25Index) -> tuple[tuple[str, str], ...]:
    return (
        (
            _BM25_STAT_KEYS["average_document_length"],
            repr(index.average_document_length),
        ),
        (_BM25_STAT_KEYS["b"], repr(index.parameters.b)),
        (_BM25_STAT_KEYS["document_count"], str(index.document_count)),
        (_BM25_STAT_KEYS["k1"], repr(index.parameters.k1)),
        (
            _BM25_STAT_KEYS["tokenizer_version"],
            index.parameters.tokenizer_version,
        ),
        (
            _BM25_STAT_KEYS["total_document_length"],
            str(index.total_document_length),
        ),
    )


def _is_valid_bm25_index(index: BM25Index) -> bool:
    document_ids = [chunk_id for chunk_id, _ in index.document_lengths]
    document_lengths = dict(index.document_lengths)
    terms = [term for term, _ in index.document_frequencies]
    document_frequencies = dict(index.document_frequencies)
    posting_keys = [(posting.term, posting.chunk_id) for posting in index.postings]

    expected_average = (
        index.total_document_length / index.document_count
        if index.document_count
        else 0.0
    )
    calculated_document_frequencies: dict[str, int] = {}
    for posting in index.postings:
        calculated_document_frequencies[posting.term] = (
            calculated_document_frequencies.get(posting.term, 0) + 1
        )

    return all(
        (
            index.document_count == len(index.document_lengths),
            len(document_ids) == len(set(document_ids)),
            index.document_lengths == tuple(sorted(index.document_lengths)),
            all(length >= 0 for length in document_lengths.values()),
            index.total_document_length == sum(document_lengths.values()),
            isclose(
                index.average_document_length,
                expected_average,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ),
            len(terms) == len(set(terms)),
            index.document_frequencies == tuple(sorted(index.document_frequencies)),
            all(
                term and 0 < frequency <= index.document_count
                for term, frequency in index.document_frequencies
            ),
            len(posting_keys) == len(set(posting_keys)),
            index.postings
            == tuple(
                sorted(
                    index.postings,
                    key=lambda posting: (posting.term, posting.chunk_id),
                )
            ),
            all(
                posting.term in document_frequencies
                and posting.chunk_id in document_lengths
                and posting.term_frequency > 0
                for posting in index.postings
            ),
            calculated_document_frequencies == document_frequencies,
        )
    )


def _symbol_from_row(row: sqlite3.Row) -> Symbol:
    return Symbol(
        id=cast(str, row[0]),
        kind=cast(str, row[1]),
        name=cast(str, row[2]),
        qualified_name=cast(str, row[3]),
        path=cast(str, row[4]),
        start_line=cast(int, row[5]),
        end_line=cast(int, row[6]),
    )


def _chunk_from_row(row: sqlite3.Row) -> Chunk:
    return Chunk(
        id=cast(str, row[0]),
        path=cast(str, row[1]),
        start_line=cast(int, row[2]),
        end_line=cast(int, row[3]),
        text=cast(str, row[4]),
        symbol_id=cast(str | None, row[5]),
        content_hash=cast(str, row[6]),
    )


def _relationship_from_row(row: sqlite3.Row) -> Relationship:
    return Relationship(
        source_id=cast(str, row[0]),
        target_id=cast(str, row[1]),
        kind=cast(str, row[2]),
        confidence=cast(float, row[3]),
        source=cast(str, row[4]),
    )
