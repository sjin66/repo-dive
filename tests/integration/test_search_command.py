from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from repo_dive.cli import main
from repo_dive.commands.search import MAX_RESULTS

FIXTURE = Path(__file__).parents[1] / "fixtures" / "index_repo"


def copy_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(
        FIXTURE,
        repository,
        ignore=shutil.ignore_patterns(".repo-dive"),
    )
    return repository


def build_index(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["index", str(repository), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["command"] == "index"


def artifact_digest(repository: Path) -> str | None:
    artifact = repository / ".repo-dive"
    if not artifact.exists():
        return None
    hasher = hashlib.sha256()
    for path in sorted(artifact.rglob("*")):
        relative = path.relative_to(artifact).as_posix()
        hasher.update(relative.encode("utf-8"))
        if path.is_symlink():
            hasher.update(b"symlink\0")
            hasher.update(path.readlink().as_posix().encode("utf-8"))
        elif path.is_file():
            hasher.update(b"file\0")
            hasher.update(path.read_bytes())
        else:
            hasher.update(b"directory\0")
    return hasher.hexdigest()


def result_document(output: str) -> dict[str, Any]:
    document = json.loads(output)
    assert isinstance(document, dict)
    return document


def test_search_returns_explainable_json_without_mutating_index(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)
    before = artifact_digest(repository)

    assert (
        main(
            [
                "search",
                str(repository),
                "greet",
                "--max-results",
                "5",
                "--format",
                "json",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    document = result_document(captured.out)
    assert captured.err == ""
    assert document["command"] == "search"
    assert document["repository"] == str(repository.resolve())
    assert document["warnings"] == []
    result = document["result"]
    assert result["query"] == "greet"
    assert result["max_results"] == 5
    assert result["result_count"] <= 5
    assert result["fusion"] == {
        "channel_weights": {"lexical": 1.0, "structural": 1.0},
        "overlap_threshold": 0.8,
        "rrf_k": 60,
        "strategy": "weighted_rrf",
    }

    hit = next(item for item in result["hits"] if item["path"] == "src/app.py")
    assert hit.keys() == {
        "chunk_id",
        "end_line",
        "fused_score",
        "lexical_score",
        "path",
        "reasons",
        "start_line",
        "structural_score",
        "symbol",
        "text",
        "vector_score",
    }
    assert hit["start_line"] >= 1
    assert hit["end_line"] >= hit["start_line"]
    assert hit["symbol"]["name"] == "greet"
    assert hit["symbol"]["qualified_name"] == "src.app.greet"
    assert "def greet" in hit["text"]
    assert hit["lexical_score"] is not None
    assert hit["structural_score"] is not None
    assert hit["vector_score"] is None
    assert hit["fused_score"] > 0
    assert hit["reasons"]
    assert artifact_digest(repository) == before


def test_search_supports_markdown_without_mutating_index(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)
    before = artifact_digest(repository)

    assert main(["search", str(repository), "format_name", "--format=markdown"]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith("# Repository search\n")
    assert '"src/utils.py":' in captured.out
    assert "src.utils.format_name" in captured.out
    assert "Fused score:" in captured.out
    assert "def format_name" in captured.out
    assert artifact_digest(repository) == before


@pytest.mark.parametrize("max_results", ["0", str(MAX_RESULTS + 1), "not-an-int"])
def test_search_rejects_invalid_result_limits_without_creating_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    max_results: str,
) -> None:
    repository = copy_fixture(tmp_path)

    assert (
        main(
            [
                "search",
                str(repository),
                "greet",
                "--max-results",
                max_results,
                "--format",
                "json",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert result_document(captured.out)["error"]["code"] == "invalid_invocation"
    assert "max-results" in captured.err
    assert artifact_digest(repository) is None


@pytest.mark.parametrize("query", ["   ", "x" * 1_001])
def test_search_rejects_empty_or_oversized_queries_before_index_access(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    query: str,
) -> None:
    repository = copy_fixture(tmp_path)

    assert main(["search", str(repository), query, "--format", "json"]) == 2

    captured = capsys.readouterr()
    assert result_document(captured.out)["error"]["code"] == "invalid_invocation"
    assert "query" in captured.err
    assert artifact_digest(repository) is None


def test_search_rejects_missing_index_without_building_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)

    assert main(["search", str(repository), "greet", "--format", "json"]) == 3

    captured = capsys.readouterr()
    assert result_document(captured.out)["error"]["code"] == "index_not_found"
    assert artifact_digest(repository) is None


def test_search_rejects_stale_index_without_replacing_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)
    (repository / "src" / "app.py").write_text(
        "def changed():\n    return True\n",
        encoding="utf-8",
    )
    before = artifact_digest(repository)

    assert main(["search", str(repository), "greet", "--format", "json"]) == 3

    captured = capsys.readouterr()
    error = result_document(captured.out)["error"]
    assert error["code"] == "index_stale"
    assert "repo-dive index" in error["message"]
    assert artifact_digest(repository) == before
