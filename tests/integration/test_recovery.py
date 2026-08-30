from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from repo_dive.cli import main
from repo_dive.wiki.models import Page
from repo_dive.wiki.service import WikiService, structure_from_document
from repo_dive.wiki.store import WikiStore

FIXTURE = Path(__file__).parents[1] / "fixtures" / "index_repo"
SOURCE_SECRET = "SOURCE_BODY_MUST_NOT_REACH_STDERR"


def copy_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(
        FIXTURE,
        repository,
        ignore=shutil.ignore_patterns(".repo-dive"),
    )
    return repository


def result_document(output: str) -> dict[str, Any]:
    document = json.loads(output)
    assert isinstance(document, dict)
    return document


def run_json(
    capsys: pytest.CaptureFixture[str], arguments: list[str]
) -> dict[str, Any]:
    assert main([*arguments, "--format", "json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return result_document(captured.out)


def artifact_digest(repository: Path) -> str:
    artifact = repository / ".repo-dive"
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


def initialize_one_page_wiki(
    repository: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_json(capsys, ["index", str(repository)])
    structure: dict[str, Any] = {
        "schema_version": "2.0",
        "title": "Recovery Wiki",
        "description": "Grounded recovery fixture.",
        "output_language": "en",
        "sections": [
            {
                "id": "guide",
                "title": "Guide",
                "pages": [
                    {
                        "id": "overview",
                        "title": "Overview",
                        "description": "Explain the greet entrypoint.",
                        "relevant_files": ["src/app.py"],
                        "related_page_ids": [],
                        "subsections": [
                            {
                                "id": "runtime_flow",
                                "title": "Runtime flow",
                                "description": "Explain the greet entrypoint.",
                                "direct_source_paths": ["src/app.py"],
                                "documentation_only": False,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    WikiService(repository).initialize(structure_from_document(structure))
    run_json(
        capsys,
        [
            "wiki",
            "evidence",
            str(repository),
            "--page",
            "overview",
            "--token-budget",
            "1200",
        ],
    )
    page: Page = WikiStore(repository).read_wiki().sections[0].pages[0]
    submission_path = tmp_path / "page.json"
    submission_path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "page_id": page.id,
                "subsections": [
                    {
                        "subsection_id": page.subsections[0].id,
                        "body": "The entrypoint delegates greeting construction.\n",
                        "evidence_ids": [page.evidence[0].evidence_id],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    run_json(
        capsys,
        [
            "wiki",
            "page",
            str(repository),
            "--page",
            "overview",
            "--input",
            str(submission_path),
        ],
    )
    run_json(capsys, ["wiki", "build", str(repository)])


def test_corrupt_sqlite_returns_stable_error_without_replacing_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    run_json(capsys, ["index", str(repository)])
    database = repository / ".repo-dive/index/index.sqlite3"
    database.write_bytes(b"CORRUPT_SQLITE_WITH_PRIVATE_BYTES")
    corrupted_digest = artifact_digest(repository)

    assert main(["search", str(repository), "greet", "--format", "json"]) == 3

    captured = capsys.readouterr()
    error = result_document(captured.out)["error"]
    assert error["code"] == "index_integrity_error"
    assert captured.err == "Published repository index failed integrity checks.\n"
    assert "PRIVATE_BYTES" not in captured.out + captured.err
    assert artifact_digest(repository) == corrupted_digest
    assert database.read_bytes() == b"CORRUPT_SQLITE_WITH_PRIVATE_BYTES"


def test_stale_index_fails_read_only_and_redacts_changed_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    run_json(capsys, ["index", str(repository)])
    app = repository / "src/app.py"
    app.write_text(f"def changed():\n    return {SOURCE_SECRET!r}\n", encoding="utf-8")
    before = artifact_digest(repository)

    assert (
        main(
            [
                "context",
                str(repository),
                "greet",
                "--token-budget",
                "256",
                "--format",
                "json",
            ]
        )
        == 3
    )

    captured = capsys.readouterr()
    assert result_document(captured.out)["error"]["code"] == "index_stale"
    assert SOURCE_SECRET not in captured.out + captured.err
    assert artifact_digest(repository) == before


def test_index_publish_failure_keeps_previous_generation_and_cleans_temporary_data(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = copy_fixture(tmp_path)
    first = run_json(capsys, ["index", str(repository)])
    pointer = repository / ".repo-dive/index"
    original_generation = pointer.resolve(strict=True)
    before = artifact_digest(repository)
    app = repository / "src/app.py"
    app.write_text(
        app.read_text(encoding="utf-8") + f"\nSECRET = {SOURCE_SECRET!r}\n",
        encoding="utf-8",
    )
    real_replace = os.replace
    pointer_replace_attempts = 0

    def fail_pointer_replace(source: str | Path, destination: str | Path) -> None:
        nonlocal pointer_replace_attempts
        if Path(destination) == pointer and pointer_replace_attempts == 0:
            pointer_replace_attempts += 1
            raise OSError("sensitive simulated failure")
        real_replace(source, destination)

    monkeypatch.setattr("repo_dive.indexing.service.os.replace", fail_pointer_replace)

    assert main(["index", str(repository), "--format", "json"]) == 4

    captured = capsys.readouterr()
    error = result_document(captured.out)["error"]
    assert error == {
        "code": "index_build_failed",
        "details": {"stage": "publish"},
        "message": "Could not build repository index.",
    }
    assert SOURCE_SECRET not in captured.out + captured.err
    assert "sensitive simulated failure" not in captured.out + captured.err
    assert pointer.resolve(strict=True) == original_generation
    assert (
        json.loads((pointer / "manifest.json").read_text(encoding="utf-8"))["build_id"]
        == first["result"]["build_id"]
    )
    assert artifact_digest(repository) == before
    assert not list((repository / ".repo-dive").glob(".index.*.tmp"))
    assert not list((repository / ".repo-dive").glob(".index.*.previous"))
    assert list((repository / ".repo-dive/index-generations").iterdir()) == [
        original_generation
    ]


def test_stale_evidence_preserves_last_valid_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_one_page_wiki(repository, tmp_path, capsys)
    markdown = repository / ".repo-dive/wiki.md"
    previous = markdown.read_bytes()
    app = repository / "src/app.py"
    app.write_text(
        app.read_text(encoding="utf-8").replace("Hello", "Welcome"),
        encoding="utf-8",
    )
    run_json(capsys, ["index", str(repository)])

    assert main(["wiki", "build", str(repository), "--format", "json"]) == 3

    captured = capsys.readouterr()
    error = result_document(captured.out)["error"]
    assert error["code"] == "wiki_evidence_stale"
    assert error["details"] == {"page_ids": ["overview"]}
    assert markdown.read_bytes() == previous
    assert not list(markdown.parent.glob(".wiki.md.*.tmp"))


def test_corrupt_wiki_json_is_not_repaired_or_disclosed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_one_page_wiki(repository, tmp_path, capsys)
    wiki_state = repository / ".repo-dive/wiki.json"
    corrupt = b'{"private":"WIKI_PRIVATE_BODY",broken\n'
    wiki_state.write_bytes(corrupt)

    assert main(["wiki", "status", str(repository), "--format", "json"]) == 3

    captured = capsys.readouterr()
    error = result_document(captured.out)["error"]
    assert error["code"] == "wiki_state_invalid"
    assert captured.err == "Repository Wiki state is invalid.\n"
    assert "WIKI_PRIVATE_BODY" not in captured.out + captured.err
    assert wiki_state.read_bytes() == corrupt


def test_wiki_markdown_replace_failure_preserves_previous_complete_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_one_page_wiki(repository, tmp_path, capsys)
    markdown = repository / ".repo-dive/wiki.md"
    previous = b"# Last valid Wiki\n"
    markdown.write_bytes(previous)

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("WIKI_PRIVATE_BODY")

    monkeypatch.setattr("repo_dive.storage.atomic.os.replace", fail_replace)

    assert main(["wiki", "build", str(repository), "--format", "json"]) == 4

    captured = capsys.readouterr()
    error = result_document(captured.out)["error"]
    assert error["code"] == "atomic_write_failed"
    assert captured.err == "Could not atomically write repository artifact.\n"
    assert "WIKI_PRIVATE_BODY" not in captured.out + captured.err
    assert markdown.read_bytes() == previous
    assert not list(markdown.parent.glob(".wiki.md.*.tmp"))
