"""Discover repository files without reading their contents."""

from __future__ import annotations

import fnmatch
import os
import stat
import subprocess
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from repo_dive.errors import RepositoryError
from repo_dive.storage.paths import resolve_repository

ScanMode = Literal["git", "filesystem"]

DEFAULT_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".repo-dive",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "vendor",
        "venv",
    }
)


@dataclass(frozen=True, slots=True)
class CandidateSet:
    """An ordered set of repository-relative candidate paths."""

    mode: ScanMode
    paths: tuple[str, ...]


def discover_candidates(
    repository: str | Path,
    *,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    excluded_directories: Collection[str] = DEFAULT_EXCLUDED_DIRECTORIES,
) -> CandidateSet:
    """Return deterministic candidate files for a selected repository root."""
    root = resolve_repository(repository)
    excluded = frozenset(excluded_directories)
    include_patterns = _normalize_patterns(include)
    exclude_patterns = _normalize_patterns(exclude)
    explicitly_included = _explicitly_included_directories(include_patterns, excluded)
    active_exclusions = excluded - explicitly_included

    if _is_git_root(root):
        mode: ScanMode = "git"
        discovered = _discover_git_paths(root)
    else:
        mode = "filesystem"
        discovered = _discover_filesystem_paths(root, active_exclusions)

    paths = {
        path
        for path in discovered
        if not _has_excluded_parent(path, active_exclusions)
        and _matches_patterns(path, include=include_patterns, exclude=exclude_patterns)
        and _is_regular_file(root, path)
    }
    return CandidateSet(mode=mode, paths=tuple(sorted(paths)))


def _is_git_root(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(root), "rev-parse", "--show-toplevel"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False

    if result.returncode != 0:
        return False
    reported_root = Path(os.fsdecode(result.stdout.rstrip(b"\r\n")))
    try:
        return reported_root.resolve(strict=True) == root
    except OSError:
        return False


def _discover_git_paths(root: Path) -> tuple[str, ...]:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                os.fspath(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "--deduplicate",
                "--full-name",
                "-z",
                "--",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        raise RepositoryError(
            "git_file_discovery_failed",
            "Could not enumerate Git repository files.",
        ) from error

    if result.returncode != 0:
        raise RepositoryError(
            "git_file_discovery_failed",
            "Could not enumerate Git repository files.",
            details={"returncode": result.returncode},
        )
    return tuple(os.fsdecode(item) for item in result.stdout.split(b"\0") if item)


def _discover_filesystem_paths(
    root: Path, excluded_directories: Collection[str]
) -> tuple[str, ...]:
    paths: list[str] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(
                directory.iterdir(), key=lambda path: os.fsencode(path.name)
            )
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    if entry.name not in excluded_directories:
                        pending.append(entry)
                elif entry.is_file():
                    paths.append(entry.relative_to(root).as_posix())
            except OSError:
                continue
    return tuple(paths)


def _has_excluded_parent(path: str, excluded_directories: Collection[str]) -> bool:
    return any(part in excluded_directories for part in PurePosixPath(path).parts[:-1])


def _matches_patterns(
    path: str, *, include: Sequence[str], exclude: Sequence[str]
) -> bool:
    is_included = not include or any(
        fnmatch.fnmatchcase(path, pattern) for pattern in include
    )
    is_excluded = any(fnmatch.fnmatchcase(path, pattern) for pattern in exclude)
    return is_included and not is_excluded


def _normalize_patterns(patterns: Sequence[str]) -> tuple[str, ...]:
    return tuple(pattern.replace("\\", "/") for pattern in patterns)


def _explicitly_included_directories(
    include: Sequence[str], excluded_directories: Collection[str]
) -> frozenset[str]:
    return frozenset(
        part
        for pattern in include
        for part in PurePosixPath(pattern).parts
        if part in excluded_directories
    )


def _is_regular_file(root: Path, relative_path: str) -> bool:
    candidate = PurePosixPath(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return False
    path = root.joinpath(*candidate.parts)
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False
