import json
from pathlib import Path

import pytest

from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.storage.atomic import atomic_write_bytes, atomic_write_json


def test_atomic_json_write_is_stable_and_leaves_no_temporary_file(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    target = atomic_write_json(
        repository,
        ".repo-dive/metadata.json",
        {"schema_version": "1.0", "repository": "仓库"},
    )

    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == {"repository": "仓库", "schema_version": "1.0"}
    assert list(target.parent.iterdir()) == [target]


def test_failed_atomic_replace_preserves_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    target = repository / ".repo-dive" / "wiki.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old wiki\n")

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("repo_dive.storage.atomic.os.replace", fail_replace)

    with pytest.raises(InternalOperationError) as exc_info:
        atomic_write_bytes(repository, ".repo-dive/wiki.md", b"new wiki\n")

    assert exc_info.value.code == "atomic_write_failed"
    assert target.read_bytes() == b"old wiki\n"
    assert list(target.parent.iterdir()) == [target]


def test_atomic_write_rejects_target_outside_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    with pytest.raises(RepositoryError) as exc_info:
        atomic_write_bytes(repository, "../outside.txt", b"not allowed")

    assert exc_info.value.code == "path_outside_repository"
    assert not (tmp_path / "outside.txt").exists()
