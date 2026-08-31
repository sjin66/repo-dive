"""Stable parsing-domain contracts and identity factories."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath
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
    """One exact, typed syntax occurrence between two symbol identities."""

    id: str
    source_id: str
    target_id: str
    kind: str
    confidence: float
    provenance: str
    path: str
    start_line: int
    end_line: int
    occurrence_discriminator: tuple[int, int, int]

    @property
    def source(self) -> str:
        """Preserve the existing retrieval provenance field contract."""
        return self.provenance


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
    provenance: str,
    path: str,
    start_line: int,
    end_line: int,
    occurrence_discriminator: tuple[int, int, int],
) -> Relationship:
    """Create a stable relationship occurrence with exact source Evidence."""
    if not source_id or not target_id or not kind or not provenance:
        raise ValueError("relationship identity fields must not be empty")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("relationship confidence must be between 0 and 1")
    _validate_posix_path(path)
    _validate_line_range(start_line, end_line)
    if (
        type(occurrence_discriminator) is not tuple
        or len(occurrence_discriminator) != 3
        or any(type(component) is not int for component in occurrence_discriminator)
        or any(component < 0 for component in occurrence_discriminator)
    ):
        raise ValueError("relationship occurrence discriminator must be non-negative")
    discriminator = tuple(str(component) for component in occurrence_discriminator)
    relationship_id = _stable_id(
        "relationship",
        source_id,
        target_id,
        kind,
        repr(confidence),
        provenance,
        path,
        str(start_line),
        str(end_line),
        *discriminator,
    )
    return Relationship(
        id=relationship_id,
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        confidence=confidence,
        provenance=provenance,
        path=path,
        start_line=start_line,
        end_line=end_line,
        occurrence_discriminator=occurrence_discriminator,
    )


def _validate_line_range(start_line: int, end_line: int) -> None:
    if start_line < 1 or end_line < start_line:
        raise ValueError("line range must be one-based, inclusive, and ordered")


def _validate_posix_path(path: str) -> None:
    candidate = PurePosixPath(path)
    if (
        not path
        or "\\" in path
        or candidate.is_absolute()
        or str(candidate) != path
        or ".." in candidate.parts
    ):
        raise ValueError("path must be a repository-relative POSIX path")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogateescape")).hexdigest()


def _stable_id(prefix: str, *parts: str) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        encoded = part.encode("utf-8", errors="surrogateescape")
        hasher.update(len(encoded).to_bytes(8, byteorder="big"))
        hasher.update(encoded)
    return f"{prefix}:{hasher.hexdigest()}"
