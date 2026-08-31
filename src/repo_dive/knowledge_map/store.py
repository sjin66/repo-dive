"""Strict artifact persistence and the one shared Knowledge Map writer lock."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Literal, Self, cast

from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.knowledge_map.models import KnowledgeMapArtifact, canonical_bytes
from repo_dive.schema import JsonObject
from repo_dive.storage.atomic import atomic_write_bytes
from repo_dive.storage.paths import resolve_repository, resolve_within_repository

MAP_ARTIFACT_PATH = ".repo-dive/knowledge-map.json"
MAP_LOCK_PATH = ".repo-dive/knowledge-map.lock"
DEFAULT_LOCK_TIMEOUT = 2.0

SnapshotState = Literal["absent", "current", "invalid"]


@dataclass(frozen=True, slots=True)
class MapSnapshot:
    """One complete observed artifact state and its CAS identity."""

    state: SnapshotState
    artifact: KnowledgeMapArtifact | None
    byte_hash: str | None
    raw_bytes: bytes | None

    @property
    def cas_identity(self) -> tuple[int, str] | str:
        if self.artifact is not None:
            return (self.artifact.artifact_revision, self.artifact.content_hash)
        return self.byte_hash or "absent"


@dataclass(frozen=True, slots=True)
class MapWriteResult:
    changed: bool
    artifact: KnowledgeMapArtifact


class MapStore:
    """Repository-confined strict reads and shared write transactions."""

    def __init__(self, repository: str | Path) -> None:
        self.repository = resolve_repository(repository)

    def read_snapshot(self) -> MapSnapshot:
        """Read one complete artifact, preserving invalid bytes for CAS recovery."""
        path = resolve_within_repository(self.repository, MAP_ARTIFACT_PATH)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return MapSnapshot("absent", None, None, None)
        except OSError as error:
            raise RepositoryError(
                "knowledge_map_invalid",
                "Knowledge Map artifact cannot be read.",
                details=_error_details("after_recovery", "preserve_and_rebuild_map"),
            ) from error
        byte_hash = "sha256:" + hashlib.sha256(data).hexdigest()
        try:
            document = json.loads(
                data.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            artifact = KnowledgeMapArtifact.from_document(document)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
            return MapSnapshot("invalid", None, byte_hash, data)
        return MapSnapshot("current", artifact, byte_hash, data)

    def read_artifact(self) -> KnowledgeMapArtifact:
        """Read a valid artifact or return a stable repository-state error."""
        snapshot = self.read_snapshot()
        if snapshot.state == "absent":
            raise RepositoryError(
                "knowledge_map_not_found",
                "Knowledge Map artifact does not exist.",
                details=_error_details("after_recovery", "build_map"),
            )
        if snapshot.artifact is None:
            raise RepositoryError(
                "knowledge_map_invalid",
                "Knowledge Map artifact is invalid.",
                details=_error_details("after_recovery", "preserve_and_rebuild_map"),
            )
        return snapshot.artifact

    def write_transaction(
        self,
        expected_snapshot: MapSnapshot,
        *,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT,
        revalidate: Callable[[], None] | None = None,
    ) -> MapWriteTransaction:
        """Create the only supported artifact writer transaction."""
        return MapWriteTransaction(
            self,
            expected_snapshot,
            lock_timeout=lock_timeout,
            revalidate=revalidate,
        )


class MapWriteTransaction:
    """Bounded lock, under-lock revalidation, equivalence, CAS, and replace."""

    def __init__(
        self,
        store: MapStore,
        expected_snapshot: MapSnapshot,
        *,
        lock_timeout: float,
        revalidate: Callable[[], None] | None,
    ) -> None:
        if lock_timeout <= 0 or lock_timeout > 60:
            raise ValueError("lock timeout must be positive and bounded")
        self._store = store
        self._expected = expected_snapshot
        self._timeout = lock_timeout
        self._revalidate = revalidate
        self._lock: BinaryIO | None = None
        self._current: MapSnapshot | None = None
        self._completed = False

    def __enter__(self) -> Self:
        lock_path = resolve_within_repository(self._store.repository, MAP_LOCK_PATH)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = lock_path.open("a+b")
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                _try_lock(self._lock)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self._lock.close()
                    self._lock = None
                    raise RepositoryError(
                        "knowledge_map_locked",
                        "Another Knowledge Map writer holds the lock.",
                        details=_error_details("unchanged", "wait_for_writer"),
                    ) from None
                time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
        try:
            self._current = self._store.read_snapshot()
            if self._revalidate is not None:
                self._revalidate()
        except BaseException:
            self._release_lock()
            raise
        return self

    def commit(
        self,
        candidate: KnowledgeMapArtifact,
        *,
        equivalent: Callable[[KnowledgeMapArtifact], bool] | None = None,
    ) -> MapWriteResult:
        """Validate and atomically publish one complete candidate at most once."""
        if self._lock is None or self._current is None:
            raise RuntimeError("write transaction is not active")
        if self._completed:
            raise RuntimeError("write transaction has already completed")
        current_artifact = self._current.artifact
        if (
            current_artifact is not None
            and equivalent is not None
            and equivalent(current_artifact)
        ):
            self._completed = True
            return MapWriteResult(False, current_artifact)
        if self._current.cas_identity != self._expected.cas_identity:
            raise RepositoryError(
                "knowledge_map_revision_conflict",
                "Knowledge Map changed after the operation began.",
                details=_error_details("after_reload", "reload_artifact"),
            )
        expected_revision = (
            current_artifact.artifact_revision + 1
            if current_artifact is not None
            else 1
        )
        if candidate.artifact_revision != expected_revision:
            raise RepositoryError(
                "knowledge_map_validation_failed",
                "Knowledge Map candidate revision is not the next revision.",
                details=_error_details("after_recovery", "rebuild_or_reset_scope"),
            )
        serialized = canonical_bytes(candidate.to_document()) + b"\n"
        if len(serialized) > candidate.capacity_limits.artifact_byte_budget:
            raise RepositoryError(
                "knowledge_map_artifact_budget_exceeded",
                "Knowledge Map exceeds its artifact byte budget.",
                details={
                    **_error_details(
                        "after_recovery", "raise_artifact_budget_or_lower_sublimits"
                    ),
                    "actual_bytes": len(serialized),
                    "budget_bytes": candidate.capacity_limits.artifact_byte_budget,
                },
            )
        try:
            atomic_write_bytes(
                self._store.repository,
                MAP_ARTIFACT_PATH,
                serialized,
            )
        except InternalOperationError as error:
            raise InternalOperationError(
                "knowledge_map_write_failed",
                "Could not publish the Knowledge Map artifact.",
                details=_error_details(
                    "after_cause_clears", "inspect_write_environment"
                ),
            ) from error
        self._completed = True
        return MapWriteResult(True, candidate)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._release_lock()

    def _release_lock(self) -> None:
        if self._lock is None:
            return
        stream = self._lock
        self._lock = None
        try:
            _unlock(stream)
        finally:
            stream.close()


def _try_lock(stream: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        if stream.read(1) == b"":
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            locking = cast(
                Callable[[int, int, int], None],
                msvcrt.locking,  # type: ignore[attr-defined]
            )
            nonblocking = cast(int, msvcrt.LK_NBLCK)  # type: ignore[attr-defined]
            locking(stream.fileno(), nonblocking, 1)
        except OSError as error:
            raise BlockingIOError from error
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(stream: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        locking = cast(
            Callable[[int, int, int], None],
            msvcrt.locking,  # type: ignore[attr-defined]
        )
        unlock = cast(int, msvcrt.LK_UNLCK)  # type: ignore[attr-defined]
        locking(stream.fileno(), unlock, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _error_details(retry_mode: str, recovery_action: str) -> JsonObject:
    return cast(
        JsonObject,
        {"recovery_action": recovery_action, "retry_mode": retry_mode},
    )
