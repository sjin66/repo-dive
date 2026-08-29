"""Offline project-scoped installation of the bundled Agent Skill."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Literal

from repo_dive.errors import InvocationError
from repo_dive.storage.paths import resolve_repository, resolve_within_repository

AgentName = Literal["claude-code", "codex", "opencode", "gemini-cli", "github-copilot"]
InstallStatus = Literal["installed", "reused", "replaced"]

SUPPORTED_AGENTS: tuple[AgentName, ...] = (
    "claude-code",
    "codex",
    "opencode",
    "gemini-cli",
    "github-copilot",
)
AGENT_DESTINATIONS: dict[AgentName, str] = {
    "claude-code": ".claude/skills/wiki",
    "codex": ".agents/skills/wiki",
    "opencode": ".agents/skills/wiki",
    "gemini-cli": ".agents/skills/wiki",
    "github-copilot": ".agents/skills/wiki",
}


@dataclass(frozen=True, slots=True)
class InstalledDestination:
    """One unique project destination and its installation outcome."""

    path: str
    agents: tuple[AgentName, ...]
    status: InstallStatus


@dataclass(frozen=True, slots=True)
class InitResult:
    """Complete result of one project initialization."""

    agents: tuple[AgentName, ...]
    destinations: tuple[InstalledDestination, ...]


def install_skill(
    repository: str | Path,
    *,
    agents: tuple[str, ...],
    source: Traversable,
    force: bool = False,
) -> InitResult:
    """Install one skill tree into deduplicated project discovery paths."""
    root = resolve_repository(repository)
    selected = _validate_agents(agents)
    source_files = _read_source_files(source)
    destinations = _group_destinations(selected)
    plans: list[tuple[str, tuple[AgentName, ...], Path, InstallStatus]] = []

    for relative_path, mapped_agents in destinations:
        destination = _safe_destination(root, relative_path)
        status = _destination_status(destination, source_files, force=force)
        plans.append((relative_path, mapped_agents, destination, status))

    _publish_plans(root, plans, source_files)

    return InitResult(
        agents=selected,
        destinations=tuple(
            InstalledDestination(path=path, agents=mapped_agents, status=status)
            for path, mapped_agents, _destination, status in plans
        ),
    )


def _validate_agents(agents: tuple[str, ...]) -> tuple[AgentName, ...]:
    selected: list[AgentName] = []
    for agent in agents:
        if agent not in SUPPORTED_AGENTS:
            raise InvocationError(
                "invalid_agent",
                f"Unsupported Agent: {agent}",
                details={"agent": agent},
            )
        typed_agent: AgentName = agent
        if typed_agent not in selected:
            selected.append(typed_agent)
    if not selected:
        raise InvocationError("agent_required", "At least one Agent must be selected.")
    return tuple(selected)


def _read_source_files(source: Traversable) -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    def visit(directory: Traversable, prefix: str = "") -> None:
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            relative_path = f"{prefix}/{child.name}" if prefix else child.name
            if child.is_dir():
                visit(child, relative_path)
            elif child.is_file():
                files[relative_path] = child.read_bytes()

    visit(source)
    if "SKILL.md" not in files:
        raise RuntimeError("Bundled wiki skill is missing SKILL.md.")
    return files


def _group_destinations(
    agents: tuple[AgentName, ...],
) -> tuple[tuple[str, tuple[AgentName, ...]], ...]:
    grouped: dict[str, list[AgentName]] = {}
    for agent in agents:
        grouped.setdefault(AGENT_DESTINATIONS[agent], []).append(agent)
    return tuple(
        (path, tuple(mapped_agents)) for path, mapped_agents in grouped.items()
    )


def _safe_destination(root: Path, relative_path: str) -> Path:
    """Reject destination symlinks instead of following them during replacement."""
    candidate = root
    parts = relative_path.split("/")
    for index, part in enumerate(parts):
        candidate /= part
        if candidate.is_symlink():
            raise InvocationError(
                "skill_conflict",
                f"Agent Skill destination contains a symbolic link: {candidate}",
                details={"path": str(candidate)},
            )
        if index < len(parts) - 1 and candidate.exists() and not candidate.is_dir():
            raise InvocationError(
                "skill_conflict",
                f"Agent Skill destination parent is not a directory: {candidate}",
                details={"path": str(candidate)},
            )
    resolve_within_repository(root, relative_path)
    return root.joinpath(*parts)


def _destination_status(
    destination: Path, source_files: dict[str, bytes], *, force: bool
) -> InstallStatus:
    if not destination.exists() and not destination.is_symlink():
        return "installed"
    if destination.is_dir() and not destination.is_symlink():
        existing_files = {
            path.relative_to(destination).as_posix(): path.read_bytes()
            for path in destination.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        has_symlinks = any(path.is_symlink() for path in destination.rglob("*"))
        if not has_symlinks and existing_files == source_files:
            return "reused"
    if force:
        return "replaced"
    raise InvocationError(
        "skill_conflict",
        f"{destination} already contains different content; use --force to replace it.",
        details={"path": str(destination)},
    )


def _remove_destination(destination: Path) -> None:
    if destination.is_dir() and not destination.is_symlink():
        shutil.rmtree(destination)
    else:
        destination.unlink()


def _publish_plans(
    root: Path,
    plans: list[tuple[str, tuple[AgentName, ...], Path, InstallStatus]],
    source_files: dict[str, bytes],
) -> None:
    """Stage all files, publish each tree atomically, and roll back on failure."""
    changed_plans = [plan for plan in plans if plan[3] != "reused"]
    if not changed_plans:
        return

    transaction = Path(tempfile.mkdtemp(prefix=".repo-dive-init-", dir=root))
    staged: list[Path] = []
    committed: list[tuple[Path, Path | None]] = []
    published = False
    try:
        for index, _plan in enumerate(changed_plans):
            stage = transaction / f"stage-{index}"
            _write_files(stage, source_files)
            staged.append(stage)

        for index, (relative_path, _agents, destination, status) in enumerate(
            changed_plans
        ):
            # Recheck immediately before publishing so a changed parent symlink
            # cannot redirect the operation outside the selected repository.
            if _safe_destination(root, relative_path) != destination:
                raise RuntimeError(
                    "Agent Skill destination changed during installation."
                )
            current_status = _destination_status(
                destination, source_files, force=status == "replaced"
            )
            if current_status != status:
                raise InvocationError(
                    "skill_conflict",
                    f"{destination} changed during installation; "
                    "no files were published.",
                    details={"path": str(destination)},
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            backup: Path | None = None
            if status == "replaced":
                backup = transaction / f"backup-{index}"
                os.replace(destination, backup)
            committed.append((destination, backup))
            os.replace(staged[index], destination)
        published = True
    except Exception as publish_error:
        rollback_errors: list[OSError] = []
        for destination, backup in reversed(committed):
            try:
                if destination.exists() or destination.is_symlink():
                    _remove_destination(destination)
                if backup is not None and backup.exists():
                    os.replace(backup, destination)
            except OSError as rollback_error:
                rollback_errors.append(rollback_error)
        if rollback_errors:
            raise RuntimeError(
                f"Agent Skill installation rollback failed; recovery files remain at "
                f"{transaction}."
            ) from publish_error
        raise
    finally:
        backups_remain = any(transaction.glob("backup-*"))
        if published or not backups_remain:
            shutil.rmtree(transaction, ignore_errors=True)


def _write_files(destination: Path, source_files: dict[str, bytes]) -> None:
    for relative_path, content in source_files.items():
        target = destination.joinpath(*relative_path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


__all__ = [
    "AGENT_DESTINATIONS",
    "SUPPORTED_AGENTS",
    "InitResult",
    "InstalledDestination",
    "install_skill",
]
