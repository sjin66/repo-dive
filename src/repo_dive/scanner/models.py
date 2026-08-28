"""Typed repository inventory contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from repo_dive.scanner.candidates import ScanMode


class ReadStatus(StrEnum):
    """Whether a candidate produced readable source text."""

    READ = "read"
    SKIPPED = "skipped"


class SkipReason(StrEnum):
    """Stable reasons why a candidate has no source text."""

    BINARY = "binary"
    TOO_LARGE = "too_large"
    UNREADABLE = "unreadable"
    INVALID_ENCODING = "invalid_encoding"


@dataclass(frozen=True, slots=True)
class FileRecord:
    """Stable metadata and read outcome for one repository file."""

    path: str
    language: str
    size_bytes: int
    content_hash: str | None
    encoding: str | None
    status: ReadStatus
    skip_reason: SkipReason | None


@dataclass(frozen=True, slots=True)
class SourceFile:
    """A file record paired with decoded text when it is readable."""

    record: FileRecord
    text: str | None


@dataclass(frozen=True, slots=True)
class Inventory:
    """A deterministic snapshot of selected repository files."""

    mode: ScanMode
    files: tuple[SourceFile, ...]
    repository_fingerprint: str
    max_file_size: int
