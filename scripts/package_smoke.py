"""Validate built distributions and smoke-test a default wheel installation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

RUNTIME_SCHEMA = "repo_dive/indexing/schema.sql"
BUNDLED_SKILL = "repo_dive/_skills/wiki/SKILL.md"
BUILT_SKILL_REFERENCE = "repo_dive/_skills/wiki/references/workflow-contract.md"
BUILT_RELEASE_METADATA = "repo_dive/_skills/wiki/references/release.json"
BUILT_POSIX_LAUNCHER = "repo_dive/_skills/wiki/scripts/repo-dive"
BUILT_POWERSHELL_LAUNCHER = "repo_dive/_skills/wiki/scripts/repo-dive.ps1"
SDIST_SKILL = "skills/wiki/SKILL.md"
SDIST_SKILL_REFERENCE = "skills/wiki/references/workflow-contract.md"
SDIST_RELEASE_METADATA = "skills/wiki/references/release.json"
SDIST_POSIX_LAUNCHER = "skills/wiki/scripts/repo-dive"
SDIST_POWERSHELL_LAUNCHER = "skills/wiki/scripts/repo-dive.ps1"
CLI_SMOKE_ARGUMENTS = (
    ("--version",),
    ("--help",),
    ("init", "--help"),
    ("index", "--help"),
    ("search", "--help"),
    ("context", "--help"),
    ("wiki", "--help"),
)


class PackageSmokeError(RuntimeError):
    """A safe, user-facing release Harness failure."""


def find_distributions(dist_dir: Path) -> tuple[Path, Path]:
    """Return the single repo-dive wheel and sdist in ``dist_dir``."""
    wheels = tuple(sorted(dist_dir.glob("repo_dive-*.whl")))
    sdists = tuple(sorted(dist_dir.glob("repo_dive-*.tar.gz")))
    if len(wheels) != 1:
        raise PackageSmokeError(
            f"expected exactly one wheel in {dist_dir}, found {len(wheels)}"
        )
    if len(sdists) != 1:
        raise PackageSmokeError(
            f"expected exactly one sdist in {dist_dir}, found {len(sdists)}"
        )
    return wheels[0], sdists[0]


def validate_wheel(wheel: Path) -> None:
    """Require the runtime SQLite schema in the built wheel."""
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = frozenset(archive.namelist())
    except (OSError, zipfile.BadZipFile) as error:
        raise PackageSmokeError(f"wheel is unreadable: {wheel.name}") from error
    if RUNTIME_SCHEMA not in names:
        raise PackageSmokeError(f"wheel is missing {RUNTIME_SCHEMA}")
    if BUNDLED_SKILL not in names:
        raise PackageSmokeError(f"wheel is missing {BUNDLED_SKILL}")
    for resource in (
        BUILT_SKILL_REFERENCE,
        BUILT_RELEASE_METADATA,
        BUILT_POSIX_LAUNCHER,
        BUILT_POWERSHELL_LAUNCHER,
    ):
        if resource not in names:
            raise PackageSmokeError(f"wheel is missing {resource}")


def validate_sdist(sdist: Path) -> None:
    """Require project metadata and the runtime SQLite schema in the sdist."""
    try:
        with tarfile.open(sdist, mode="r:gz") as archive:
            names = tuple(archive.getnames())
    except (OSError, tarfile.TarError) as error:
        raise PackageSmokeError(f"sdist is unreadable: {sdist.name}") from error
    if not any(name.endswith(f"/src/{RUNTIME_SCHEMA}") for name in names):
        raise PackageSmokeError(f"sdist is missing src/{RUNTIME_SCHEMA}")
    if not any(name.endswith("/pyproject.toml") for name in names):
        raise PackageSmokeError("sdist is missing pyproject.toml")
    if not any(name.endswith(f"/{SDIST_SKILL}") for name in names):
        raise PackageSmokeError(f"sdist is missing {SDIST_SKILL}")
    for resource in (
        SDIST_SKILL_REFERENCE,
        SDIST_RELEASE_METADATA,
        SDIST_POSIX_LAUNCHER,
        SDIST_POWERSHELL_LAUNCHER,
    ):
        if not any(name.endswith(f"/{resource}") for name in names):
            raise PackageSmokeError(f"sdist is missing {resource}")


def smoke_wheel_install(wheel: Path) -> None:
    """Install one wheel with default dependencies and run the public CLI surface."""
    with tempfile.TemporaryDirectory(prefix="repo-dive-wheel-smoke-") as directory:
        environment = Path(directory) / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_executable(environment, "python")
        cli = _venv_executable(environment, "repo-dive")
        _run(
            python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            os.fspath(wheel.resolve()),
            timeout=300,
        )
        _run(
            python,
            "-c",
            "import importlib.util; "
            "raise SystemExit(importlib.util.find_spec('sentence_transformers') "
            "is not None)",
        )
        for arguments in CLI_SMOKE_ARGUMENTS:
            _run(cli, *arguments)
        repository = Path(directory) / "repository"
        repository.mkdir()
        init_arguments = (
            cli,
            "init",
            ".",
            "--agent",
            "claude-code",
            "--agent",
            "codex",
            "--format",
            "json",
        )
        _run(*init_arguments, cwd=repository)
        claude_skill = repository / ".claude/skills/wiki/SKILL.md"
        shared_skill = repository / ".agents/skills/wiki/SKILL.md"
        if not claude_skill.is_file() or not shared_skill.is_file():
            raise PackageSmokeError("wheel-installed init did not install wiki skill")
        claude_reference = (
            repository / ".claude/skills/wiki/references/workflow-contract.md"
        )
        shared_reference = (
            repository / ".agents/skills/wiki/references/workflow-contract.md"
        )
        if not claude_reference.is_file() or not shared_reference.is_file():
            raise PackageSmokeError("wheel-installed init omitted a skill reference")
        if claude_skill.read_bytes() != shared_skill.read_bytes():
            raise PackageSmokeError("wheel-installed skill destinations differ")
        if claude_reference.read_bytes() != shared_reference.read_bytes():
            raise PackageSmokeError("wheel-installed skill references differ")
        authoritative = Path("skills/wiki/SKILL.md")
        if (
            authoritative.is_file()
            and claude_skill.read_bytes() != authoritative.read_bytes()
        ):
            raise PackageSmokeError(
                "wheel-installed skill differs from authoritative source"
            )
        authoritative_reference = Path("skills/wiki/references/workflow-contract.md")
        if (
            authoritative_reference.is_file()
            and claude_reference.read_bytes() != authoritative_reference.read_bytes()
        ):
            raise PackageSmokeError(
                "wheel-installed skill reference differs from authoritative source"
            )
        for source in Path("skills/wiki").rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to("skills/wiki")
            installed = repository / ".agents/skills/wiki" / relative
            if not installed.is_file() or installed.read_bytes() != source.read_bytes():
                raise PackageSmokeError(
                    f"wheel-installed skill resource differs: {relative.as_posix()}"
                )
        repeated = json.loads(_run(*init_arguments, cwd=repository))
        statuses = {
            destination["status"] for destination in repeated["result"]["destinations"]
        }
        if statuses != {"reused"}:
            raise PackageSmokeError("wheel-installed init rerun did not report reuse")


def _venv_executable(environment: Path, name: str) -> Path:
    directory = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return environment / directory / f"{name}{suffix}"


def _run(*command: str | Path, timeout: int = 60, cwd: Path | None = None) -> str:
    arguments = tuple(os.fspath(item) for item in command)
    try:
        completed = subprocess.run(
            arguments,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        command_text = " ".join(arguments)
        raise PackageSmokeError(f"command could not run: {command_text}") from error
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip() or completed.stdout.strip()
        suffix = f": {diagnostic}" if diagnostic else ""
        raise PackageSmokeError(
            f"command failed ({completed.returncode}): {' '.join(arguments)}{suffix}"
        )
    return completed.stdout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="directory containing exactly one repo-dive wheel and sdist",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        wheel, sdist = find_distributions(args.dist_dir)
        validate_wheel(wheel)
        validate_sdist(sdist)
        smoke_wheel_install(wheel)
    except PackageSmokeError as error:
        print(f"package smoke error: {error}", file=sys.stderr)
        return 1
    print(f"Package smoke OK: {wheel.name}, {sdist.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
