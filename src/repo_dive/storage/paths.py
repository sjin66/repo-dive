"""Repository-root validation and safe path resolution."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from repo_dive.errors import RepositoryError


def resolve_repository(path: str | Path) -> Path:
    """Resolve and validate an explicitly selected repository directory."""
    candidate = Path(path)
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as error:
        raise RepositoryError(
            "repository_not_found",
            "Repository path does not exist.",
            details={"path": str(candidate)},
        ) from error
    except OSError as error:
        raise RepositoryError(
            "repository_unavailable",
            "Repository path is not available.",
            details={"path": str(candidate)},
        ) from error

    if not resolved.is_dir():
        raise RepositoryError(
            "repository_not_directory",
            "Repository path is not a directory.",
            details={"path": str(candidate)},
        )
    return resolved


def _parse_relative_path(path: str | Path) -> PurePosixPath:
    text = str(path).replace("\\", "/")
    candidate = PurePosixPath(text)
    has_windows_drive = bool(candidate.parts and candidate.parts[0].endswith(":"))
    if candidate.is_absolute() or has_windows_drive or ".." in candidate.parts:
        raise RepositoryError(
            "path_outside_repository",
            "Path must stay within the selected repository.",
            details={"path": text},
        )
    return candidate


def _is_within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def resolve_within_repository(
    repository: str | Path,
    relative_path: str | Path,
    *,
    must_exist: bool = False,
) -> Path:
    """Resolve a repository-relative path without permitting an escape."""
    root = resolve_repository(repository)
    relative = _parse_relative_path(relative_path)
    unresolved = root.joinpath(*relative.parts)
    try:
        resolved = unresolved.resolve(strict=must_exist)
    except FileNotFoundError as error:
        raise RepositoryError(
            "repository_path_not_found",
            "Requested repository path does not exist.",
            details={"path": relative.as_posix()},
        ) from error
    except OSError as error:
        raise RepositoryError(
            "repository_path_unavailable",
            "Requested repository path is not available.",
            details={"path": relative.as_posix()},
        ) from error

    if not _is_within(root, resolved):
        raise RepositoryError(
            "path_outside_repository",
            "Path must stay within the selected repository.",
            details={"path": relative.as_posix()},
        )
    return resolved


def to_repository_relative_path(
    repository: str | Path, candidate_path: str | Path
) -> str:
    """Return a repository-relative POSIX path for an internal path."""
    root = resolve_repository(repository)
    candidate = Path(candidate_path)
    if candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
        if not _is_within(root, resolved):
            raise RepositoryError(
                "path_outside_repository",
                "Path must stay within the selected repository.",
                details={"path": str(candidate)},
            )
    else:
        resolved = resolve_within_repository(root, candidate)
    return resolved.relative_to(root).as_posix()
