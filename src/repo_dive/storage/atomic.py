"""Atomic writes constrained to an explicitly selected repository."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from repo_dive.errors import InternalOperationError
from repo_dive.schema import JsonObject, serialize_json_document
from repo_dive.storage.paths import (
    resolve_repository,
    resolve_within_repository,
    to_repository_relative_path,
)


def atomic_write_bytes(
    repository: str | Path, relative_path: str | Path, data: bytes
) -> Path:
    """Atomically replace one repository-owned file with complete bytes."""
    root = resolve_repository(repository)
    target = resolve_within_repository(root, relative_path)
    display_path = to_repository_relative_path(root, target)
    temporary: Path | None = None

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target = resolve_within_repository(root, relative_path)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        with os.fdopen(file_descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
    except OSError as error:
        details: JsonObject = {"path": display_path}
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                details["temporary_cleanup_failed"] = True
        raise InternalOperationError(
            "atomic_write_failed",
            "Could not atomically write repository artifact.",
            details=details,
        ) from error

    return target


def atomic_write_text(
    repository: str | Path,
    relative_path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write complete text using an explicit encoding."""
    return atomic_write_bytes(repository, relative_path, text.encode(encoding))


def atomic_write_json(
    repository: str | Path, relative_path: str | Path, value: object
) -> Path:
    """Serialize a complete stable JSON document before writing it."""
    document = serialize_json_document(value)
    return atomic_write_text(repository, relative_path, document)
