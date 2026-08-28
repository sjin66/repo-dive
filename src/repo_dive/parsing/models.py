"""Stable parsing-domain contracts and identity factories."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from repo_dive.scanner.models import FileRecord


@dataclass(frozen=True, slots=True)
class Chunk:
    """A source excerpt with an inclusive one-based line range."""

    id: str
    path: str
    start_line: int
    end_line: int
    text: str
    symbol_id: str | None
    content_hash: str


@dataclass(frozen=True, slots=True)
class Symbol:
    """A named source symbol with a stable repository identity."""

    id: str
    kind: str
    name: str
    qualified_name: str
    path: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class Relationship:
    """A typed, sourced edge between two symbol identities."""

    source_id: str
    target_id: str
    kind: str
    confidence: float
    source: str


@dataclass(frozen=True, slots=True)
class ParseDiagnostic:
    """A stable parser warning tied to a repository path."""

    code: str
    message: str
    path: str
    line: int | None = None


@dataclass(frozen=True, slots=True)
class ParseResult:
    """The complete deterministic output of one parser adapter."""

    chunks: tuple[Chunk, ...] = ()
    symbols: tuple[Symbol, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    diagnostics: tuple[ParseDiagnostic, ...] = ()


class ParserAdapter(Protocol):
    """A parser that operates only on an inventory record and decoded text."""

    def parse(self, file: FileRecord, text: str) -> ParseResult:
        """Parse one decoded source file without performing I/O."""
        ...


def create_chunk(
    *,
    path: str,
    start_line: int,
    end_line: int,
    text: str,
    symbol_id: str | None = None,
) -> Chunk:
    """Create a content-addressed chunk after validating its line range."""
    _validate_line_range(start_line, end_line)
    content_hash = _sha256(text)
    chunk_id = _stable_id(
        "chunk",
        path,
        str(start_line),
        str(end_line),
        content_hash,
        symbol_id or "",
    )
    return Chunk(
        id=chunk_id,
        path=path,
        start_line=start_line,
        end_line=end_line,
        text=text,
        symbol_id=symbol_id,
        content_hash=content_hash,
    )


def create_symbol(
    *,
    kind: str,
    name: str,
    qualified_name: str,
    path: str,
    start_line: int,
    end_line: int,
) -> Symbol:
    """Create a stable symbol identity from its semantic location."""
    _validate_line_range(start_line, end_line)
    symbol_id = _stable_id(
        "symbol",
        path,
        kind,
        qualified_name,
        str(start_line),
        str(end_line),
    )
    return Symbol(
        id=symbol_id,
        kind=kind,
        name=name,
        qualified_name=qualified_name,
        path=path,
        start_line=start_line,
        end_line=end_line,
    )


def create_relationship(
    *,
    source_id: str,
    target_id: str,
    kind: str,
    confidence: float,
    source: str,
) -> Relationship:
    """Create a relationship with a bounded confidence score."""
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("relationship confidence must be between 0 and 1")
    return Relationship(
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        confidence=confidence,
        source=source,
    )


def _validate_line_range(start_line: int, end_line: int) -> None:
    if start_line < 1 or end_line < start_line:
        raise ValueError("line range must be one-based, inclusive, and ordered")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogateescape")).hexdigest()


def _stable_id(prefix: str, *parts: str) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        encoded = part.encode("utf-8", errors="surrogateescape")
        hasher.update(len(encoded).to_bytes(8, byteorder="big"))
        hasher.update(encoded)
    return f"{prefix}:{hasher.hexdigest()}"
