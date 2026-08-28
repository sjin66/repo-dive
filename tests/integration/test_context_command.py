from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

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


def test_context_returns_stable_complete_evidence_without_mutating_index(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)
    before = artifact_digest(repository)
    arguments = [
        "context",
        str(repository),
        "greet",
        "--token-budget",
        "1200",
        "--max-results",
        "5",
        "--format",
        "json",
    ]

    assert main(arguments) == 0
    first_capture = capsys.readouterr()
    assert main(arguments) == 0
    second_capture = capsys.readouterr()

    assert first_capture.err == second_capture.err == ""
    assert first_capture.out == second_capture.out
    document = result_document(first_capture.out)
    assert document["schema_version"] == "1.0"
    assert document["command"] == "context"
    assert document["repository"] == str(repository.resolve())
    assert document["warnings"] == []
    result = document["result"]
    assert result.keys() == {
        "estimated_tokens",
        "estimator",
        "excluded",
        "fusion",
        "items",
        "max_results",
        "query",
        "reserved_tokens",
        "result_count",
        "token_budget",
        "truncated",
    }
    assert result["query"] == "greet"
    assert result["token_budget"] == 1200
    assert result["max_results"] == 5
    assert result["estimated_tokens"] <= result["token_budget"]
    assert result["reserved_tokens"] <= result["estimated_tokens"]
    assert result["estimator"] == "conservative_utf8_bytes_v1"
    assert result["result_count"] == len(result["items"])
    assert result["excluded"].keys() == {"budget", "duplicate", "low_score"}
    assert result["fusion"] == {
        "channel_weights": {"lexical": 1.0, "structural": 1.0},
        "overlap_threshold": 0.8,
        "rrf_k": 60,
        "strategy": "weighted_rrf",
    }

    item = next(item for item in result["items"] if item["path"] == "src/app.py")
    assert item.keys() == {
        "chunk_id",
        "end_line",
        "estimated_tokens",
        "evidence_id",
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
    assert item["evidence_id"].startswith("evidence:")
    assert item["start_line"] >= 1
    assert item["end_line"] >= item["start_line"]
    assert item["symbol"]["qualified_name"] == "src.app.greet"
    assert "def greet" in item["text"]
    assert item["estimated_tokens"] > 0
    assert item["fused_score"] > 0
    assert item["reasons"]
    assert artifact_digest(repository) == before


def test_context_tiny_budget_returns_empty_truncated_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)

    assert (
        main(
            [
                "context",
                str(repository),
                "greet",
                "--token-budget",
                "1",
                "--format",
                "json",
            ]
        )
        == 0
    )

    result = result_document(capsys.readouterr().out)["result"]
    assert result["items"] == []
    assert result["result_count"] == 0
    assert result["estimated_tokens"] == 1
    assert result["truncated"] is True
    assert result["excluded"]["budget"] > 0


def test_context_supports_markdown_with_grounded_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)

    assert (
        main(
            [
                "context",
                str(repository),
                "format_name",
                "--token-budget",
                "1200",
                "--format=markdown",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith("# Repository context\n")
    assert "Token budget: 1200" in captured.out
    assert "conservative_utf8_bytes_v1" in captured.out
    assert '"src/utils.py":' in captured.out
    assert "src.utils.format_name" in captured.out
    assert "Evidence ID:" in captured.out
    assert "def format_name" in captured.out


@pytest.mark.parametrize("token_budget", ["0", "-1", "not-an-int"])
def test_context_rejects_invalid_budget_before_index_access(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    token_budget: str,
) -> None:
    repository = copy_fixture(tmp_path)

    assert (
        main(
            [
                "context",
                str(repository),
                "greet",
                "--token-budget",
                token_budget,
                "--format",
                "json",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert result_document(captured.out)["error"]["code"] == "invalid_invocation"
    assert "positive integer" in captured.err
    assert artifact_digest(repository) is None


def test_context_requires_budget_and_a_current_index(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)

    assert main(["context", str(repository), "greet", "--format", "json"]) == 2
    missing_budget = capsys.readouterr()
    assert result_document(missing_budget.out)["error"]["code"] == "invalid_invocation"
    assert "token-budget" in missing_budget.err

    assert (
        main(
            [
                "context",
                str(repository),
                "greet",
                "--token-budget",
                "1200",
                "--format",
                "json",
            ]
        )
        == 3
    )
    missing_index = capsys.readouterr()
    assert result_document(missing_index.out)["error"]["code"] == "index_not_found"
    assert artifact_digest(repository) is None
