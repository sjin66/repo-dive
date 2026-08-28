from pathlib import Path

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.storage.paths import (
    resolve_repository,
    resolve_within_repository,
    to_repository_relative_path,
)


def test_resolve_repository_rejects_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(RepositoryError) as exc_info:
        resolve_repository(missing)

    assert exc_info.value.code == "repository_not_found"


def test_resolve_repository_rejects_regular_file(tmp_path: Path) -> None:
    file_path = tmp_path / "source.py"
    file_path.write_text("pass\n", encoding="utf-8")

    with pytest.raises(RepositoryError) as exc_info:
        resolve_repository(file_path)

    assert exc_info.value.code == "repository_not_directory"


def test_resolve_repository_reports_unavailable_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    def fail_resolve(path: Path, *, strict: bool = False) -> Path:
        raise PermissionError("simulated permission failure")

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    with pytest.raises(RepositoryError) as exc_info:
        resolve_repository(repository)

    assert exc_info.value.code == "repository_unavailable"


@pytest.mark.parametrize("unsafe_path", ["../outside.py", "/tmp/outside.py"])
def test_resolve_within_repository_rejects_path_escape(
    tmp_path: Path, unsafe_path: str
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    with pytest.raises(RepositoryError) as exc_info:
        resolve_within_repository(repository, unsafe_path)

    assert exc_info.value.code == "path_outside_repository"


def test_resolve_within_repository_rejects_symlink_escape(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("SECRET = True\n", encoding="utf-8")
    (repository / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RepositoryError) as exc_info:
        resolve_within_repository(repository, "linked/secret.py", must_exist=True)

    assert exc_info.value.code == "path_outside_repository"


def test_repository_relative_path_normalizes_windows_separators(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    source = repository / "src" / "repo_dive" / "cli.py"
    source.parent.mkdir(parents=True)
    source.write_text("pass\n", encoding="utf-8")

    resolved = resolve_within_repository(
        repository, "src\\repo_dive\\cli.py", must_exist=True
    )

    assert resolved == source
    assert to_repository_relative_path(repository, resolved) == "src/repo_dive/cli.py"
