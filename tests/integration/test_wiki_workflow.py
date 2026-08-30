from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from repo_dive.cli import main
from repo_dive.indexing.service import load_published_index
from repo_dive.wiki.models import Page
from repo_dive.wiki.service import WikiService, structure_from_document
from repo_dive.wiki.store import WikiStore

FIXTURE = Path(__file__).parents[1] / "fixtures" / "index_repo"


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


def copy_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(
        FIXTURE,
        repository,
        ignore=shutil.ignore_patterns(".repo-dive"),
    )
    return repository


def initialize_wiki(
    repository: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_json(capsys, ["index", str(repository)])
    structure: dict[str, Any] = {
        "schema_version": "2.0",
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
                        "description": "Explain the greet application entrypoint.",
                        "relevant_files": ["src/app.py"],
                        "related_page_ids": ["utilities"],
                        "subsections": [
                            {
                                "id": "runtime_flow",
                                "title": "Runtime flow",
                                "description": "Trace the application entrypoint.",
                                "direct_source_paths": ["src/app.py"],
                                "documentation_only": False,
                            }
                        ],
                    },
                    {
                        "id": "utilities",
                        "title": "Utilities",
                        "description": "Explain the format_name helper.",
                        "relevant_files": ["src/utils.py"],
                        "related_page_ids": ["overview"],
                        "subsections": [
                            {
                                "id": "formatting_flow",
                                "title": "Formatting",
                                "description": "Explain the formatting helper.",
                                "direct_source_paths": ["src/utils.py"],
                                "documentation_only": False,
                            }
                        ],
                    },
                ],
            }
        ],
    }
    WikiService(repository).initialize(structure_from_document(structure))


def page_by_id(repository: Path, page_id: str) -> Page:
    wiki = WikiStore(repository).read_wiki()
    return next(
        page
        for section in wiki.sections
        for page in section.pages
        if page.id == page_id
    )


def generate_page(
    repository: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    page_id: str,
    body: str,
    *,
    max_results: int = 5,
) -> None:
    run_json(
        capsys,
        [
            "wiki",
            "evidence",
            str(repository),
            "--page",
            page_id,
            "--token-budget",
            "1200",
            "--max-results",
            str(max_results),
        ],
    )
    page = page_by_id(repository, page_id)
    submission = {
        "schema_version": "2.0",
        "page_id": page_id,
        "subsections": [
            {
                "subsection_id": page.subsections[0].id,
                "body": body,
                "evidence_ids": [page.evidence[0].evidence_id],
            }
        ],
    }
    input_path = tmp_path / f"{page_id}.json"
    input_path.write_text(json.dumps(submission), encoding="utf-8")
    run_json(
        capsys,
        [
            "wiki",
            "page",
            str(repository),
            "--page",
            page_id,
            "--input",
            str(input_path),
        ],
    )


def generate_all_pages(
    repository: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    max_results: int = 5,
) -> None:
    generate_page(
        repository,
        tmp_path,
        capsys,
        "overview",
        "The entrypoint delegates greeting construction.\n",
        max_results=max_results,
    )
    generate_page(
        repository,
        tmp_path,
        capsys,
        "utilities",
        "The utility helper formats a supplied name.\n",
        max_results=max_results,
    )


def test_complete_wiki_workflow_builds_stable_markdown_and_markdown_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    generate_all_pages(repository, tmp_path, capsys)

    result = run_json(capsys, ["wiki", "build", str(repository)])

    artifact = repository / ".repo-dive/wiki.md"
    markdown = artifact.read_text(encoding="utf-8")
    assert result["command"] == "wiki build"
    assert result["result"] == {
        "artifact_path": ".repo-dive/wiki.md",
        "bytes": len(markdown.encode("utf-8")),
        "changed": True,
        "page_count": 2,
        "section_count": 1,
        "sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        "source_count": 2,
        "index_build_id": result["result"]["index_build_id"],
        "repository_fingerprint": result["result"]["repository_fingerprint"],
        "source_commit": None,
        "source_control": "non_git",
        "source_dirty": None,
    }
    assert markdown.startswith("# Example Wiki\n\nGrounded repository documentation.")
    assert markdown.index("### Overview") < markdown.index("### Utilities")
    assert "## Contents" in markdown
    assert "#### Related pages" in markdown
    assert "#### Sources" in markdown
    assert "../src/app.py#L" in markdown
    assert "../src/utils.py#L" in markdown
    first_bytes = artifact.read_bytes()

    repeated = run_json(capsys, ["wiki", "build", str(repository)])

    assert repeated["result"]["changed"] is False
    assert artifact.read_bytes() == first_bytes
    assert main(["wiki", "build", str(repository), "--format", "markdown"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == markdown
    assert artifact.read_bytes() == first_bytes
    status = run_json(capsys, ["wiki", "status", str(repository)])
    assert status["result"]["complete"] is True


def test_wiki_build_rejects_incomplete_pages_and_preserves_previous_artifact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    artifact = repository / ".repo-dive/wiki.md"
    artifact.write_bytes(b"previous wiki\n")

    assert main(["wiki", "build", str(repository), "--format", "json"]) == 3

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == "wiki_build_incomplete"
    assert error["details"]["page_ids"] == ["overview", "utilities"]
    assert artifact.read_bytes() == b"previous wiki\n"


def test_wiki_build_rejects_stale_evidence_and_preserves_current_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    generate_all_pages(repository, tmp_path, capsys, max_results=1)
    run_json(capsys, ["wiki", "build", str(repository)])
    artifact = repository / ".repo-dive/wiki.md"
    current = artifact.read_bytes()
    app_path = repository / "src/app.py"
    app_path.write_text(
        app_path.read_text(encoding="utf-8").replace("Hello", "Welcome"),
        encoding="utf-8",
    )
    run_json(capsys, ["index", str(repository)])

    assert main(["wiki", "build", str(repository), "--format", "json"]) == 3

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == "wiki_evidence_stale"
    assert error["details"]["page_ids"] == ["overview"]
    assert artifact.read_bytes() == current


def test_wiki_build_atomic_replace_failure_preserves_previous_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    generate_all_pages(repository, tmp_path, capsys)
    artifact = repository / ".repo-dive/wiki.md"
    artifact.write_bytes(b"previous wiki\n")

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("repo_dive.storage.atomic.os.replace", fail_replace)

    assert main(["wiki", "build", str(repository), "--format", "json"]) == 4

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == "atomic_write_failed"
    assert artifact.read_bytes() == b"previous wiki\n"
    assert list(artifact.parent.glob(".wiki.md.*.tmp")) == []


def test_wiki_build_rejects_index_change_between_validation_and_publish(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    generate_all_pages(repository, tmp_path, capsys)
    run_json(capsys, ["wiki", "build", str(repository)])
    artifact = repository / ".repo-dive/wiki.md"
    current = artifact.read_bytes()
    published = load_published_index(repository)
    changed = replace(
        published,
        manifest=replace(published.manifest, build_id="concurrent-build"),
    )
    snapshots = iter((published, changed))
    monkeypatch.setattr(
        "repo_dive.wiki.service.load_published_index",
        lambda repository_path: next(snapshots),
    )

    assert main(["wiki", "build", str(repository), "--format", "json"]) == 3

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == "index_changed_during_operation"
    assert artifact.read_bytes() == current


def test_wiki_build_rejects_current_index_identity_that_differs_from_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    generate_all_pages(repository, tmp_path, capsys)
    artifact = repository / ".repo-dive/wiki.md"
    artifact.write_bytes(b"previous wiki\n")
    published = load_published_index(repository)
    changed = replace(
        published,
        manifest=replace(
            published.manifest,
            build_id="equivalent-content-rebuild",
            source_control="git",
            source_commit="b" * 40,
            source_dirty=False,
        ),
    )
    monkeypatch.setattr(
        "repo_dive.wiki.service.load_published_index", lambda repository_path: changed
    )

    assert main(["wiki", "build", str(repository), "--format", "json"]) == 3

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == "wiki_evidence_stale"
    assert artifact.read_bytes() == b"previous wiki\n"
