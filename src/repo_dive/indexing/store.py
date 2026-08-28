"""Typed SQLite storage for the private repository index."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from types import TracebackType
from typing import cast

from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.parsing.models import Chunk, ParseResult, Relationship, Symbol
from repo_dive.scanner.models import (
    FileRecord,
    ReadStatus,
    SkipReason,
    SourceFile,
)

INDEX_SCHEMA_VERSION = 1


class IndexStore:
    """The only supported connection boundary for the private SQLite index."""

    def __init__(self, database: Path, connection: sqlite3.Connection) -> None:
        self.database = database
        self._connection = connection
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
        _validate_document_path(source.record.path, parsed)
        try:
            with self._transaction():
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
            "(id, file_path, ordinal, kind, name, qualified_name, "
            "start_line, end_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    symbol.id,
                    file_path,
                    ordinal,
                    symbol.kind,
                    symbol.name,
                    symbol.qualified_name,
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


def _connect(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(path, isolation_level=None)
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
