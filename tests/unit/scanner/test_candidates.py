from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from repo_dive.scanner.candidates import discover_candidates

FIXTURE_REPOSITORY = Path(__file__).parents[2] / "fixtures" / "scanner_repo"


@pytest.fixture(autouse=True)
def isolated_git_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)


def initialize_git_repository(repository: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet", str(repository)],
        check=True,
        capture_output=True,
    )


def write_file(
    repository: Path, relative_path: str, content: str = "content\n"
) -> None:
    target = repository / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_git_candidates_include_tracked_and_unignored_untracked_files(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    initialize_git_repository(repository)
    write_file(repository, ".gitignore", "ignored.py\n")
    write_file(repository, "tracked.py")
    write_file(repository, "visible.py")
    write_file(repository, "ignored.py")
    subprocess.run(
        ["git", "-C", str(repository), "add", ".gitignore", "tracked.py"],
        check=True,
        capture_output=True,
    )

    candidates = discover_candidates(repository)

    assert candidates.mode == "git"
    assert candidates.paths == (".gitignore", "tracked.py", "visible.py")


def test_git_candidates_parse_nul_delimited_unusual_filenames(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    initialize_git_repository(repository)
    expected = ("line\nbreak.py", "space name.py", "unicodé.py")
    for relative_path in expected:
        write_file(repository, relative_path)

    candidates = discover_candidates(repository)

    assert candidates.mode == "git"
    assert candidates.paths == tuple(sorted(expected))


def test_filesystem_candidates_apply_default_directory_exclusions(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    write_file(repository, "README.md")
    write_file(repository, "src/main.py")
    for excluded_path in (
        ".git/config",
        ".repo-dive/wiki.md",
        ".venv/lib/package.py",
        "venv/lib/package.py",
        "__pycache__/module.pyc",
        ".pytest_cache/state",
        "node_modules/package/index.js",
        "vendor/package/source.py",
        "build/generated.py",
        "dist/package.whl",
    ):
        write_file(repository, excluded_path)

    candidates = discover_candidates(repository)

    assert candidates.mode == "filesystem"
    assert candidates.paths == ("README.md", "src/main.py")


def test_candidates_apply_include_and_exclude_patterns(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    write_file(repository, "docs/guide.md")
    write_file(repository, "src/main.py")
    write_file(repository, "src/test_main.py")

    candidates = discover_candidates(
        repository,
        include=("src/*.py",),
        exclude=("*test_*",),
    )

    assert candidates.paths == ("src/main.py",)


def test_explicit_include_can_override_a_default_directory_exclusion(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    write_file(repository, ".repo-dive/wiki.md")
    write_file(repository, ".repo-dive/state.json")

    candidates = discover_candidates(
        repository,
        include=(".repo-dive/*.md",),
    )

    assert candidates.paths == (".repo-dive/wiki.md",)


def test_selected_subdirectory_of_git_repository_uses_filesystem_mode(
    tmp_path: Path,
) -> None:
    initialize_git_repository(tmp_path)
    repository = tmp_path / "service"
    repository.mkdir()
    write_file(repository, "main.py")

    candidates = discover_candidates(repository)

    assert candidates.mode == "filesystem"
    assert candidates.paths == ("main.py",)


def test_filesystem_candidates_do_not_follow_symlinks(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    write_file(outside, "secret.py")
    (repository / "linked.py").symlink_to(outside / "secret.py")

    candidates = discover_candidates(repository)

    assert candidates.paths == ()


def test_fixture_has_same_recorded_paths_in_git_and_filesystem_modes(
    tmp_path: Path,
) -> None:
    git_repository = tmp_path / "git-repository"
    shutil.copytree(FIXTURE_REPOSITORY, git_repository)
    initialize_git_repository(git_repository)

    filesystem_candidates = discover_candidates(FIXTURE_REPOSITORY)
    git_candidates = discover_candidates(git_repository)

    assert filesystem_candidates.mode == "filesystem"
    assert git_candidates.mode == "git"
    assert filesystem_candidates.paths == git_candidates.paths == ("README.md",)
