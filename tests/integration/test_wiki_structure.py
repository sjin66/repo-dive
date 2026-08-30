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


def structure_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "title": "Example Wiki",
        "description": "Grounded repository documentation.",
        "output_language": "en",
        "sections": [
            {
                "id": "guide",
                "title": "Guide",
                "pages": [
                    {
                        "id": "overview",
                        "title": "Overview",
                        "description": "Explain the application entrypoint.",
                        "relevant_files": ["src/app.py"],
                        "related_page_ids": ["utilities"],
                    },
                    {
                        "id": "utilities",
                        "title": "Utilities",
                        "description": "Explain formatting helpers.",
                        "relevant_files": ["src/utils.py"],
                        "related_page_ids": ["overview"],
                    },
                ],
            },
        ],
    }


def write_structure(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "structure.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def result_document(output: str) -> dict[str, Any]:
    document = json.loads(output)
    assert isinstance(document, dict)
    return document


def artifact_digest(repository: Path) -> str:
    artifact = repository / ".repo-dive"
    hasher = hashlib.sha256()
    for path in sorted(artifact.rglob("*")):
        relative = path.relative_to(artifact).as_posix()
        hasher.update(relative.encode("utf-8"))
        if path.is_file():
            hasher.update(path.read_bytes())
        else:
            hasher.update(b"directory\0")
    return hasher.hexdigest()


def submit_structure(
    repository: Path,
    input_path: Path,
) -> int:
    return main(
        [
            "wiki",
            "structure",
            str(repository),
            "--input",
            str(input_path),
            "--format",
            "json",
        ]
    )


def test_wiki_structure_creates_versioned_state_and_is_byte_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)
    input_path = write_structure(tmp_path, structure_document())

    assert submit_structure(repository, input_path) == 0
    first_capture = capsys.readouterr()
    first_digest = artifact_digest(repository)
    assert submit_structure(repository, input_path) == 0
    second_capture = capsys.readouterr()

    first = result_document(first_capture.out)
    second = result_document(second_capture.out)
    assert first["command"] == second["command"] == "wiki structure"
    assert first["repository"] == str(repository.resolve())
    assert first["result"]["changed"] is True
    assert first["result"]["created_page_ids"] == ["overview", "utilities"]
    assert second["result"]["changed"] is False
    assert artifact_digest(repository) == first_digest

    wiki_document = json.loads(
        (repository / ".repo-dive/wiki.json").read_text(encoding="utf-8")
    )
    metadata_document = json.loads(
        (repository / ".repo-dive/metadata.json").read_text(encoding="utf-8")
    )
    assert wiki_document["schema_version"] == "1.0"
    assert wiki_document["sections"][0]["pages"][0]["status"] == "pending"
    assert wiki_document["sections"][0]["pages"][0]["body"] is None
    assert metadata_document["schema_version"] == "1.0"
    assert metadata_document["wiki_schema_version"] == "1.0"
    assert metadata_document["index_schema_version"] == 4
    assert metadata_document["index_build_id"]
    assert metadata_document["repository"] == str(repository.resolve())


def test_structure_change_invalidates_only_affected_page_in_legacy_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)
    document = structure_document()
    input_path = write_structure(tmp_path, document)
    assert submit_structure(repository, input_path) == 0
    capsys.readouterr()
    document["sections"][0]["pages"][0]["description"] = (
        "Explain the application entrypoint and call flow."
    )
    document["sections"][0]["pages"].reverse()
    write_structure(tmp_path, document)

    assert submit_structure(repository, input_path) == 0

    result = result_document(capsys.readouterr().out)["result"]
    assert result["changed"] is True
    assert result["invalidated_page_ids"] == ["overview"]
    updated = json.loads(
        (repository / ".repo-dive/wiki.json").read_text(encoding="utf-8")
    )
    pages_by_id = {page["id"]: page for page in updated["sections"][0]["pages"]}
    overview = pages_by_id["overview"]
    utilities = pages_by_id["utilities"]
    assert [page["id"] for page in updated["sections"][0]["pages"]] == [
        "utilities",
        "overview",
    ]
    assert overview["status"] == "pending"
    assert overview["description"].endswith("call flow.")
    assert utilities["status"] == "pending"


def test_governed_commands_reject_legacy_state_without_rewriting_bytes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)
    input_path = write_structure(tmp_path, structure_document())
    assert submit_structure(repository, input_path) == 0
    capsys.readouterr()
    before = artifact_digest(repository)
    page_path = tmp_path / "page.json"
    page_path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "page_id": "overview",
                "subsections": [
                    {
                        "subsection_id": "any",
                        "body": "Evidence-grounded content.",
                        "evidence_ids": ["evidence:unresolved"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    commands = (
        ["wiki", "status", str(repository)],
        ["wiki", "validate", str(repository)],
        ["wiki", "build", str(repository)],
        [
            "wiki",
            "evidence",
            str(repository),
            "--page",
            "overview",
            "--token-budget",
            "100",
        ],
        [
            "wiki",
            "page",
            str(repository),
            "--page",
            "overview",
            "--input",
            str(page_path),
        ],
    )

    for command in commands:
        assert main([*command, "--format", "json"]) == 3
        error = result_document(capsys.readouterr().out)["error"]
        assert error["code"] == "wiki_state_version_unsupported"
        assert artifact_digest(repository) == before


@pytest.mark.parametrize("invalid_kind", ["unknown_path", "duplicate_page"])
def test_structure_rejects_invalid_references_without_public_wiki_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    invalid_kind: str,
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)
    document = structure_document()
    if invalid_kind == "unknown_path":
        document["sections"][0]["pages"][0]["relevant_files"] = ["src/missing.py"]
        expected_code = "wiki_relevant_file_unknown"
    else:
        document["sections"][0]["pages"][1]["id"] = "overview"
        document["sections"][0]["pages"][0]["related_page_ids"] = []
        document["sections"][0]["pages"][1]["related_page_ids"] = []
        expected_code = "wiki_structure_invalid"
    input_path = write_structure(tmp_path, document)

    assert submit_structure(repository, input_path) == 2

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == expected_code
    assert not (repository / ".repo-dive/wiki.json").exists()
    assert not (repository / ".repo-dive/metadata.json").exists()


def test_structure_requires_valid_json_and_a_current_index(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    input_path = tmp_path / "structure.json"
    input_path.write_text("{broken\n", encoding="utf-8")

    assert submit_structure(repository, input_path) == 2
    invalid = capsys.readouterr()
    assert result_document(invalid.out)["error"]["code"] == (
        "wiki_structure_input_invalid"
    )
    assert "{broken" not in invalid.err

    input_path = write_structure(tmp_path, structure_document())
    assert submit_structure(repository, input_path) == 3
    missing_index = capsys.readouterr()
    assert result_document(missing_index.out)["error"]["code"] == "index_not_found"
    assert not (repository / ".repo-dive/wiki.json").exists()


def test_wiki_status_rejects_uninitialized_repository(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)

    assert main(["wiki", "status", str(repository), "--format", "json"]) == 3

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == "wiki_not_initialized"


def test_deprecated_structure_rejects_governed_state_without_rewriting_bytes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    build_index(repository, capsys)
    assert (
        main(
            [
                "wiki",
                "init",
                str(repository),
                "--locale",
                "en",
                "--template",
                "general_mixed",
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    before = artifact_digest(repository)
    input_path = write_structure(tmp_path, structure_document())

    assert submit_structure(repository, input_path) == 3

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == "wiki_state_version_unsupported"
    assert artifact_digest(repository) == before
