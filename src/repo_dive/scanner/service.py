"""Read and classify deterministic repository candidates."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from repo_dive.errors import InvocationError
from repo_dive.scanner.candidates import ScanMode, discover_candidates
from repo_dive.scanner.models import (
    FileRecord,
    Inventory,
    ReadStatus,
    SkipReason,
    SourceFile,
)
from repo_dive.storage.paths import resolve_repository

DEFAULT_MAX_FILE_SIZE = 1_000_000
READ_CHUNK_SIZE = 64 * 1024

_LANGUAGE_BY_SUFFIX = {
    ".bash": "shell",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".css": "css",
    ".go": "go",
    ".h": "c",
    ".hpp": "cpp",
    ".html": "html",
    ".java": "java",
    ".js": "javascript",
    ".json": "json",
    ".jsonl": "json",
    ".jsx": "jsx",
    ".md": "markdown",
    ".mdx": "markdown",
    ".py": "python",
    ".pyi": "python",
    ".rs": "rust",
    ".sh": "shell",
    ".sql": "sql",
    ".toml": "toml",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".txt": "text",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".zsh": "shell",
}

_LANGUAGE_BY_FILENAME = {
    "dockerfile": "dockerfile",
    "gemfile": "ruby",
    "makefile": "makefile",
}


@dataclass(frozen=True, slots=True)
class _ReadResult:
    size_bytes: int
    content_hash: str | None
    content: bytes | None
    error: bool = False


def scan_repository(
    repository: str | Path,
    *,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> Inventory:
    """Read repository candidates into an ordered, fingerprinted inventory."""
    if max_file_size <= 0:
        raise InvocationError(
            "invalid_max_file_size",
            "Maximum file size must be greater than zero.",
            details={"max_file_size": max_file_size},
        )

    root = resolve_repository(repository)
    candidates = discover_candidates(root, include=include, exclude=exclude)
    files = tuple(
        _scan_file(root, relative_path, max_file_size=max_file_size)
        for relative_path in candidates.paths
    )
    fingerprint = _inventory_fingerprint(
        mode=candidates.mode,
        files=files,
        max_file_size=max_file_size,
    )
    return Inventory(
        mode=candidates.mode,
        files=files,
        repository_fingerprint=fingerprint,
        max_file_size=max_file_size,
    )


def detect_language(relative_path: str) -> str:
    """Return a stable language name based only on a repository-relative path."""
    path = PurePosixPath(relative_path)
    filename = path.name.lower()
    if filename in _LANGUAGE_BY_FILENAME:
        return _LANGUAGE_BY_FILENAME[filename]
    return _LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "unknown")


def _scan_file(root: Path, relative_path: str, *, max_file_size: int) -> SourceFile:
    language = detect_language(relative_path)
    path = root.joinpath(*PurePosixPath(relative_path).parts)
    result = _read_file(path, max_file_size=max_file_size)

    if result.error:
        return _skipped_file(
            relative_path,
            size_bytes=result.size_bytes,
            language=language,
            content_hash=None,
            reason=SkipReason.UNREADABLE,
        )
    if result.content is None:
        return _skipped_file(
            relative_path,
            size_bytes=result.size_bytes,
            language=language,
            content_hash=result.content_hash,
            reason=SkipReason.TOO_LARGE,
        )
    if b"\x00" in result.content:
        return _skipped_file(
            relative_path,
            size_bytes=result.size_bytes,
            language=language,
            content_hash=result.content_hash,
            reason=SkipReason.BINARY,
        )

    encoding = "utf-8-sig" if result.content.startswith(b"\xef\xbb\xbf") else "utf-8"
    try:
        text = result.content.decode(encoding, errors="strict")
    except UnicodeDecodeError:
        return _skipped_file(
            relative_path,
            size_bytes=result.size_bytes,
            language=language,
            content_hash=result.content_hash,
            reason=SkipReason.INVALID_ENCODING,
        )

    record = FileRecord(
        path=relative_path,
        size_bytes=result.size_bytes,
        language=language,
        content_hash=result.content_hash,
        encoding=encoding,
        status=ReadStatus.READ,
        skip_reason=None,
    )
    return SourceFile(record=record, text=text)


def _read_file(path: Path, *, max_file_size: int) -> _ReadResult:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        file_descriptor = os.open(path, flags)
    except OSError:
        return _ReadResult(
            size_bytes=_best_effort_size(path),
            content_hash=None,
            content=None,
            error=True,
        )

    hasher = hashlib.sha256()
    content = bytearray()
    size_bytes = 0
    too_large = False
    try:
        metadata = os.fstat(file_descriptor)
        if not _is_same_regular_file(path, metadata):
            return _ReadResult(0, None, None, error=True)
        while True:
            chunk = os.read(file_descriptor, READ_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
            size_bytes += len(chunk)
            if not too_large and size_bytes <= max_file_size:
                content.extend(chunk)
            else:
                too_large = True
                content.clear()
    except OSError:
        return _ReadResult(size_bytes, None, None, error=True)
    finally:
        with suppress(OSError):
            os.close(file_descriptor)

    return _ReadResult(
        size_bytes=size_bytes,
        content_hash=hasher.hexdigest(),
        content=None if too_large else bytes(content),
    )


def _is_same_regular_file(path: Path, opened_metadata: os.stat_result) -> bool:
    try:
        path_metadata = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISREG(opened_metadata.st_mode)
        and stat.S_ISREG(path_metadata.st_mode)
        and (opened_metadata.st_dev, opened_metadata.st_ino)
        == (path_metadata.st_dev, path_metadata.st_ino)
    )


def _best_effort_size(path: Path) -> int:
    try:
        return path.lstat().st_size
    except OSError:
        return 0


def _skipped_file(
    path: str,
    *,
    size_bytes: int,
    language: str,
    content_hash: str | None,
    reason: SkipReason,
) -> SourceFile:
    return SourceFile(
        record=FileRecord(
            path=path,
            size_bytes=size_bytes,
            language=language,
            content_hash=content_hash,
            encoding=None,
            status=ReadStatus.SKIPPED,
            skip_reason=reason,
        ),
        text=None,
    )


def _inventory_fingerprint(
    *,
    mode: ScanMode,
    files: tuple[SourceFile, ...],
    max_file_size: int,
) -> str:
    payload = {
        "files": [
            {
                "content_hash": source.record.content_hash,
                "encoding": source.record.encoding,
                "language": source.record.language,
                "path": source.record.path,
                "size_bytes": source.record.size_bytes,
                "skip_reason": (
                    source.record.skip_reason.value
                    if source.record.skip_reason is not None
                    else None
                ),
                "status": source.record.status.value,
            }
            for source in files
        ],
        "max_file_size": max_file_size,
        "mode": mode,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(serialized).hexdigest()
