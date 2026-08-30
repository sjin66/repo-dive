from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import IndexService, load_published_index


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
    )


def test_index_captures_clean_and_dirty_git_source_identity(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
    _git(repository, "init", "-q")
    _git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "add",
        "app.py",
    )
    _git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-qm",
        "initial",
    )

    IndexService().build(repository)
    clean = load_published_index(repository).manifest
    assert clean.source_control == "git"
    assert clean.source_commit is not None and len(clean.source_commit) == 40
    assert clean.source_dirty is False

    (repository / "app.py").write_text("value = 2\n", encoding="utf-8")
    IndexService().build(repository)
    dirty = load_published_index(repository).manifest
    assert dirty.source_commit == clean.source_commit
    assert dirty.source_dirty is True


def test_index_marks_non_git_source_explicitly(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")

    IndexService().build(repository)

    manifest = load_published_index(repository).manifest
    assert manifest.source_control == "non_git"
    assert manifest.source_commit is None
    assert manifest.source_dirty is None


def test_index_captures_untracked_file_and_unborn_git_identity(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    (repository / "untracked.py").write_text("value = 1\n", encoding="utf-8")

    IndexService().build(repository)

    manifest = load_published_index(repository).manifest
    assert manifest.source_control == "git"
    assert manifest.source_commit is None
    assert manifest.source_dirty is True
    assert "untracked.py" in {item.path for item in manifest.files}


def test_git_source_identity_probe_failure_aborts_indexing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
    _git(repository, "init", "-q")
    real_run = cast(Callable[..., subprocess.CompletedProcess[bytes]], subprocess.run)

    def fail_identity(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        if "rev-parse" in arguments and "--verify" in arguments:
            raise OSError("probe failed")
        return real_run(arguments, **kwargs)

    monkeypatch.setattr("repo_dive.indexing.service.subprocess.run", fail_identity)

    with pytest.raises(RepositoryError) as captured:
        IndexService().build(repository)
    assert captured.value.code == "git_source_identity_failed"
