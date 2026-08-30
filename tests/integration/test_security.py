from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from repo_dive.cli import main
from repo_dive.commands.wiki import MAX_STRUCTURE_INPUT_BYTES

FIXTURE = Path(__file__).parents[1] / "fixtures" / "security_repo"
OUTSIDE_SECRET = "OUTSIDE_SOURCE_MUST_NOT_BE_INDEXED"


def copy_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE, repository)
    return repository


def result_document(output: str) -> dict[str, Any]:
    document = json.loads(output)
    assert isinstance(document, dict)
    return document


def artifact_digest(repository: Path) -> str | None:
    artifact = repository / ".repo-dive"
    if not artifact.exists() and not artifact.is_symlink():
        return None
    hasher = hashlib.sha256()
    for path in sorted(artifact.rglob("*")):
        hasher.update(path.relative_to(artifact).as_posix().encode("utf-8"))
        if path.is_symlink():
            hasher.update(b"symlink\0" + str(path.readlink()).encode("utf-8"))
        elif path.is_file():
            hasher.update(b"file\0" + path.read_bytes())
        else:
            hasher.update(b"directory\0")
    return hasher.hexdigest()


def test_index_rejects_artifact_symlink_escape_without_disclosing_outside_data(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text(OUTSIDE_SECRET, encoding="utf-8")
    (repository / ".repo-dive").symlink_to(outside, target_is_directory=True)

    assert main(["index", str(repository), "--format", "json"]) == 3

    captured = capsys.readouterr()
    error = result_document(captured.out)["error"]
    assert error["code"] == "path_outside_repository"
    assert captured.err == "Path must stay within the selected repository.\n"
    assert OUTSIDE_SECRET not in captured.out + captured.err
    assert list(outside.iterdir()) == [sentinel]
    assert sentinel.read_text(encoding="utf-8") == OUTSIDE_SECRET


def test_hostile_sources_stay_inside_repository_and_context_budget(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    source = repository / "src"
    source.mkdir()
    (source / "app.py").write_text(
        "def safe_value():\n    return 'inside'\n", encoding="utf-8"
    )
    hostile_name = "space name.py" if os.name == "nt" else "line\nbreak.py"
    (source / hostile_name).write_text(
        "def odd_name():\n    return 'safe'\n", encoding="utf-8"
    )
    (source / "invalid.py").write_bytes(b"def hidden():\n    return '\xff'\n")
    (source / "large.py").write_bytes(b"x" * 256)
    outside = tmp_path / "outside.py"
    outside.write_text(
        f"def stolen():\n    return {OUTSIDE_SECRET!r}\n", encoding="utf-8"
    )
    if os.name != "nt":
        (source / "escape.py").symlink_to(outside)

    assert (
        main(
            [
                "index",
                str(repository),
                "--max-file-size",
                "128",
                "--format",
                "json",
            ]
        )
        == 0
    )
    indexed_capture = capsys.readouterr()
    result = result_document(indexed_capture.out)["result"]
    assert indexed_capture.err == ""
    assert result["files"] == 5
    assert result["indexed_files"] == 3
    assert result["skipped_files"] == 2
    assert OUTSIDE_SECRET not in indexed_capture.out

    manifest = json.loads(
        (repository / ".repo-dive/index/manifest.json").read_text(encoding="utf-8")
    )
    files = {item["path"]: item for item in manifest["files"]}
    assert "src/escape.py" not in files
    assert files["src/invalid.py"]["status"] == "skipped"
    assert files["src/large.py"]["status"] == "skipped"
    assert f"src/{hostile_name}" in files

    assert (
        main(
            [
                "context",
                str(repository),
                "safe_value",
                "--token-budget",
                "256",
                "--format",
                "json",
            ]
        )
        == 0
    )
    context_capture = capsys.readouterr()
    context = result_document(context_capture.out)["result"]
    assert context_capture.err == ""
    assert context["estimated_tokens"] <= context["token_budget"] == 256
    assert OUTSIDE_SECRET not in context_capture.out

    assert main(["search", str(repository), "odd_name", "--format", "json"]) == 0
    search_capture = capsys.readouterr()
    search = result_document(search_capture.out)["result"]
    assert search_capture.err == ""
    assert any(item["path"] == f"src/{hostile_name}" for item in search["hits"])


@pytest.mark.parametrize("attack", ["traversal", "oversized"])
def test_wiki_structure_rejects_hostile_input_without_mutating_index(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    attack: str,
) -> None:
    repository = copy_fixture(tmp_path)
    assert main(["index", str(repository), "--format", "json"]) == 0
    capsys.readouterr()
    before = artifact_digest(repository)
    structure_path = tmp_path / "structure.json"
    if attack == "oversized":
        structure_path.write_bytes(b"{" + b"x" * MAX_STRUCTURE_INPUT_BYTES)
        expected_code = "wiki_structure_input_too_large"
    else:
        structure_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "title": "Unsafe",
                    "description": "Traversal must be rejected.",
                    "output_language": "en",
                    "sections": [
                        {
                            "id": "guide",
                            "title": "Guide",
                            "pages": [
                                {
                                    "id": "escape",
                                    "title": "Escape",
                                    "description": "Attempt traversal.",
                                    "relevant_files": ["../outside.py"],
                                    "related_page_ids": [],
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        expected_code = "wiki_structure_invalid"

    assert (
        main(
            [
                "wiki",
                "structure",
                str(repository),
                "--input",
                str(structure_path),
                "--format",
                "json",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert result_document(captured.out)["error"]["code"] == expected_code
    assert "../outside.py" not in captured.err
    assert artifact_digest(repository) == before
    assert not (repository / ".repo-dive/wiki.json").exists()
    assert not (repository / ".repo-dive/metadata.json").exists()
