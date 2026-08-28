from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from repo_dive.cli import main
from repo_dive.errors import RepositoryError
from repo_dive.wiki.models import Page, PageStatus
from repo_dive.wiki.store import WikiStore
from repo_dive.wiki.validation import stale_page_ids, validate_page_evidence

FIXTURE = Path(__file__).parents[1] / "fixtures" / "index_repo"


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


def build_index(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> dict[str, Any]:
    return run_json(capsys, ["index", str(repository)])


def write_structure(tmp_path: Path) -> Path:
    document = {
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
                        "description": "Explain the greet application entrypoint.",
                        "relevant_files": ["src/app.py"],
                        "related_page_ids": ["utilities"],
                    },
                    {
                        "id": "utilities",
                        "title": "Utilities",
                        "description": "Explain the format_name helper.",
                        "relevant_files": ["src/utils.py"],
                        "related_page_ids": ["overview"],
                    },
                ],
            }
        ],
    }
    path = tmp_path / "structure.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def initialize_wiki(
    repository: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_index(repository, capsys)
    run_json(
        capsys,
        [
            "wiki",
            "structure",
            str(repository),
            "--input",
            str(write_structure(tmp_path)),
        ],
    )


def collect_evidence(
    repository: Path,
    page_id: str,
    capsys: pytest.CaptureFixture[str],
    *,
    token_budget: int = 1_200,
    max_results: int = 5,
) -> dict[str, Any]:
    return run_json(
        capsys,
        [
            "wiki",
            "evidence",
            str(repository),
            "--page",
            page_id,
            "--token-budget",
            str(token_budget),
            "--max-results",
            str(max_results),
        ],
    )


def artifact_digest(repository: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted((repository / ".repo-dive").rglob("*")):
        hasher.update(path.relative_to(repository).as_posix().encode("utf-8"))
        if path.is_file():
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def page_by_id(repository: Path, page_id: str) -> Page:
    wiki = WikiStore(repository).read_wiki()
    return next(
        page
        for section in wiki.sections
        for page in section.pages
        if page.id == page_id
    )


def test_wiki_evidence_persists_reproducible_bundle_before_returning_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)

    document = collect_evidence(repository, "overview", capsys)

    assert document["command"] == "wiki evidence"
    result = document["result"]
    assert result["page_id"] == "overview"
    assert result["status"] == "evidence_ready"
    assert result["query"] == (
        "Overview\nExplain the greet application entrypoint.\npath:src/app.py"
    )
    assert result["token_budget"] == 1_200
    assert result["max_results"] == 5
    assert result["index_schema_version"] == 4
    assert result["index_build_id"]
    assert result["generated_at"].endswith("Z")
    assert result["items"]
    item = next(item for item in result["items"] if item["path"] == "src/app.py")
    assert item["content_hash"]
    assert "def greet" in item["text"]

    page = page_by_id(repository, "overview")
    assert page.status is PageStatus.EVIDENCE_READY
    assert page.error is None
    assert page.evidence
    assert all(reference.content_hash for reference in page.evidence)
    assert page.evidence_snapshot is not None
    assert page.evidence_snapshot.query == result["query"]
    assert page.evidence_snapshot.index_build_id == result["index_build_id"]
    assert page.evidence_snapshot.retrieval.max_results == 5
    assert page.evidence_snapshot.generated_at == result["generated_at"]
    assert page_by_id(repository, "utilities").status is PageStatus.PENDING

    assert (
        main(
            [
                "wiki",
                "evidence",
                str(repository),
                "--page",
                "overview",
                "--token-budget",
                "1200",
                "--format",
                "markdown",
            ]
        )
        == 0
    )
    markdown = capsys.readouterr().out
    assert markdown.startswith("# Wiki evidence\n")
    assert "Page ID: `overview`" in markdown
    assert "Evidence ID:" in markdown
    assert "def greet" in markdown


def test_wiki_evidence_empty_result_fails_only_requested_page(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)

    arguments = [
        "wiki",
        "evidence",
        str(repository),
        "--page",
        "overview",
        "--token-budget",
        "1",
        "--format",
        "json",
    ]
    assert main(arguments) == 3

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == "wiki_evidence_empty"
    overview = page_by_id(repository, "overview")
    utilities = page_by_id(repository, "utilities")
    assert overview.status is PageStatus.FAILED
    assert overview.error == "wiki_evidence_empty"
    assert utilities.status is PageStatus.PENDING
    assert utilities.error is None


def test_wiki_evidence_rejects_unknown_page_without_mutating_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    before = artifact_digest(repository)

    assert (
        main(
            [
                "wiki",
                "evidence",
                str(repository),
                "--page",
                "missing",
                "--token-budget",
                "1200",
                "--format",
                "json",
            ]
        )
        == 2
    )

    error = result_document(capsys.readouterr().out)["error"]
    assert error["code"] == "wiki_page_unknown"
    assert artifact_digest(repository) == before


def test_changed_chunk_stales_only_dependent_page_and_blocks_consumers(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    collect_evidence(repository, "overview", capsys, max_results=1)
    collect_evidence(repository, "utilities", capsys, max_results=1)
    previous = WikiStore(repository).read_wiki()

    app_path = repository / "src/app.py"
    app_path.write_text(
        app_path.read_text(encoding="utf-8").replace("Hello", "Welcome"),
        encoding="utf-8",
    )
    build_index(repository, capsys)

    assert stale_page_ids(repository, previous) == ("overview",)
    overview = next(
        page for page in previous.sections[0].pages if page.id == "overview"
    )
    utilities = next(
        page for page in previous.sections[0].pages if page.id == "utilities"
    )
    with pytest.raises(RepositoryError) as captured:
        validate_page_evidence(repository, overview)
    assert captured.value.code == "wiki_evidence_stale"
    validate_page_evidence(repository, utilities)

    structure_result = run_json(
        capsys,
        [
            "wiki",
            "structure",
            str(repository),
            "--input",
            str(write_structure(tmp_path)),
        ],
    )["result"]
    assert structure_result["invalidated_page_ids"] == ["overview"]
    assert structure_result["preserved_page_ids"] == ["utilities"]

    collect_evidence(repository, "utilities", capsys)

    assert page_by_id(repository, "overview").status is PageStatus.PENDING
    assert page_by_id(repository, "utilities").status is PageStatus.EVIDENCE_READY
