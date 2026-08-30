from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from repo_dive.cli import main

FIXTURE = Path(__file__).parents[1] / "fixtures" / "index_repo"


def copy_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(
        FIXTURE,
        repository,
        ignore=shutil.ignore_patterns(".repo-dive"),
    )
    return repository


def test_index_command_reports_counts_versions_and_idempotent_reuse(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)

    assert main(["index", str(repository), "--format", "json"]) == 0
    first_capture = capsys.readouterr()
    first = json.loads(first_capture.out)

    assert first_capture.err == ""
    assert first["command"] == "index"
    assert first["warnings"] == []
    assert first["result"]["files"] == 3
    assert first["result"]["indexed_files"] == 3
    assert first["result"]["chunks"] > 0
    assert first["result"]["symbols"] > 0
    assert first["result"]["relationships"] >= 0
    assert first["result"]["rebuilt_files"] == 3
    assert first["result"]["reused_files"] == 0
    assert first["result"]["index_schema_version"] == 4
    assert first["result"]["manifest_schema_version"] == "2.0"

    assert main(["index", str(repository), "--format=json"]) == 0
    second = json.loads(capsys.readouterr().out)

    assert second["result"]["build_id"] == first["result"]["build_id"]
    assert second["result"]["rebuilt_files"] == 0
    assert second["result"]["reused_files"] == 3
    assert second["result"]["deleted_files"] == 0


def test_index_command_rejects_invalid_repository_before_artifact_creation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository_file = tmp_path / "not-a-repository"
    repository_file.write_text("not a directory", encoding="utf-8")

    assert main(["index", str(repository_file), "--format", "json"]) == 3

    captured = capsys.readouterr()
    assert json.loads(captured.out)["error"]["code"] == "repository_not_directory"
    assert not (tmp_path / ".repo-dive").exists()


def test_index_command_rejects_non_positive_limits_as_bad_invocation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)

    assert main(["index", str(repository), "--max-file-size", "0"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "positive integer" in captured.err
    assert not (repository / ".repo-dive").exists()


def test_index_command_supports_markdown_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)

    assert main(["index", str(repository), "--format", "markdown"]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith("# Repository index\n")
    assert "- Rebuilt files: 3" in captured.out
    assert "- Index Schema: 4" in captured.out
