from __future__ import annotations

import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from repo_dive.cli import main
from repo_dive.commands.wiki import MAX_PAGE_INPUT_BYTES
from repo_dive.wiki.models import Page, PageStatus
from repo_dive.wiki.service import WikiService, structure_from_document
from repo_dive.wiki.store import WikiStore

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


def collect_evidence(
    repository: Path,
    page_id: str,
    capsys: pytest.CaptureFixture[str],
    *,
    max_results: int = 5,
) -> Page:
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
    return page_by_id(repository, page_id)


def page_by_id(repository: Path, page_id: str) -> Page:
    wiki = WikiStore(repository).read_wiki()
    return next(
        page
        for section in wiki.sections
        for page in section.pages
        if page.id == page_id
    )


def write_submission(
    tmp_path: Path,
    page: Page,
    *,
    body: str = "##### Details\n\nThe entrypoint calls `greet`.\n",
    page_id: str | None = None,
    evidence_ids: list[str] | None = None,
    filename: str = "page.json",
) -> Path:
    document = {
        "schema_version": "2.0",
        "page_id": page.id if page_id is None else page_id,
        "subsections": [
            {
                "subsection_id": page.subsections[0].id,
                "body": body,
                "evidence_ids": (
                    [page.evidence[0].evidence_id]
                    if evidence_ids is None
                    else evidence_ids
                ),
            }
        ],
    }
    path = tmp_path / filename
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def submit_arguments(repository: Path, page_id: str, input_path: str) -> list[str]:
    return [
        "wiki",
        "page",
        str(repository),
        "--page",
        page_id,
        "--input",
        input_path,
    ]


def test_wiki_page_persists_body_and_citations_and_retries_idempotently(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    evidence_page = collect_evidence(repository, "overview", capsys)
    body = "##### Details\n\nThe entrypoint delegates greeting construction.\n"
    input_path = write_submission(tmp_path, evidence_page, body=body)

    document = run_json(
        capsys,
        submit_arguments(repository, "overview", str(input_path)),
    )

    assert document["command"] == "wiki page"
    result = document["result"]
    assert result == {
        "body_bytes": len(body.encode("utf-8")),
        "changed": True,
        "citation_count": 1,
        "evidence_ids": [evidence_page.evidence[0].evidence_id],
        "page_id": "overview",
        "status": "generated",
    }
    assert body not in document
    persisted = page_by_id(repository, "overview")
    assert persisted.status is PageStatus.GENERATED
    assert persisted.body is None
    assert persisted.subsection_contents[0].body == body
    assert persisted.citation_ids == (evidence_page.evidence[0].evidence_id,)
    assert persisted.error is None
    before_wiki = (repository / ".repo-dive/wiki.json").read_bytes()
    before_metadata = (repository / ".repo-dive/metadata.json").read_bytes()

    repeated = run_json(
        capsys,
        submit_arguments(repository, "overview", str(input_path)),
    )

    assert repeated["result"]["changed"] is False
    assert (repository / ".repo-dive/wiki.json").read_bytes() == before_wiki
    assert (repository / ".repo-dive/metadata.json").read_bytes() == before_metadata


def test_wiki_page_accepts_bounded_json_from_stdin(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    page = collect_evidence(repository, "overview", capsys)
    body = "##### Details\n\nGenerated through stdin.\n"
    document = {
        "schema_version": "2.0",
        "page_id": "overview",
        "subsections": [
            {
                "subsection_id": page.subsections[0].id,
                "body": body,
                "evidence_ids": [page.evidence[0].evidence_id],
            }
        ],
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(document)))

    result = run_json(capsys, submit_arguments(repository, "overview", "-"))

    assert result["result"]["status"] == "generated"
    persisted = page_by_id(repository, "overview")
    assert persisted.body is None
    assert persisted.subsection_contents[0].body == body


def test_failed_page_can_be_corrected_without_changing_generated_pages(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    overview = collect_evidence(repository, "overview", capsys)
    utilities = collect_evidence(repository, "utilities", capsys)
    overview_input = write_submission(tmp_path, overview, filename="overview.json")
    run_json(
        capsys,
        submit_arguments(repository, "overview", str(overview_input)),
    )
    generated_overview = json.dumps(
        page_by_id(repository, "overview").to_document(),
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    oversized = write_submission(
        tmp_path,
        utilities,
        body="x" * 200_001,
        filename="oversized.json",
    )

    assert (
        main(
            [
                *submit_arguments(repository, "utilities", str(oversized)),
                "--format",
                "json",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    error = result_document(captured.out)["error"]
    assert error["code"] == "wiki_page_body_too_large"
    assert "x" * 1_000 not in captured.out
    assert "x" * 1_000 not in captured.err
    assert page_by_id(repository, "utilities").status is PageStatus.EVIDENCE_READY

    corrected = write_submission(
        tmp_path,
        utilities,
        body="##### Details\n\nThe helper formats a name.\n",
        filename="corrected.json",
    )
    run_json(
        capsys,
        submit_arguments(repository, "utilities", str(corrected)),
    )

    assert page_by_id(repository, "utilities").status is PageStatus.GENERATED
    unchanged_overview = json.dumps(
        page_by_id(repository, "overview").to_document(),
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    assert unchanged_overview == generated_overview


def test_wiki_page_rejects_wrong_page_and_unknown_evidence_without_disclosure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    page = collect_evidence(repository, "overview", capsys)
    private_body = "Do not echo this complete page.\n"
    wrong_page = write_submission(
        tmp_path,
        page,
        body=private_body,
        page_id="utilities",
        filename="wrong-page.json",
    )

    assert (
        main(
            [
                *submit_arguments(repository, "overview", str(wrong_page)),
                "--format",
                "json",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert result_document(captured.out)["error"]["code"] == "wiki_page_id_mismatch"
    assert private_body not in captured.out
    assert private_body not in captured.err
    assert page_by_id(repository, "overview").status is PageStatus.EVIDENCE_READY

    unknown_evidence = write_submission(
        tmp_path,
        page,
        body=private_body,
        evidence_ids=["evidence:not-owned-by-this-page"],
        filename="unknown-evidence.json",
    )
    assert (
        main(
            [
                *submit_arguments(repository, "overview", str(unknown_evidence)),
                "--format",
                "json",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert (
        result_document(captured.out)["error"]["code"] == "wiki_page_evidence_unknown"
    )
    assert private_body not in captured.out
    assert private_body not in captured.err
    unchanged = page_by_id(repository, "overview")
    assert unchanged.status is PageStatus.EVIDENCE_READY
    assert unchanged.error is None


def test_wiki_page_rejects_invalid_utf8_and_invalid_state_without_mutation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b'{"body":"\xff"}')
    before = (repository / ".repo-dive/wiki.json").read_bytes()

    assert (
        main(
            [
                *submit_arguments(repository, "overview", str(invalid)),
                "--format",
                "json",
            ]
        )
        == 2
    )
    assert (
        result_document(capsys.readouterr().out)["error"]["code"]
        == "wiki_page_input_invalid"
    )
    assert (repository / ".repo-dive/wiki.json").read_bytes() == before

    too_large = tmp_path / "too-large.json"
    too_large.write_bytes(b"{" + b" " * MAX_PAGE_INPUT_BYTES)
    assert (
        main(
            [
                *submit_arguments(repository, "overview", str(too_large)),
                "--format",
                "json",
            ]
        )
        == 2
    )
    assert (
        result_document(capsys.readouterr().out)["error"]["code"]
        == "wiki_page_input_too_large"
    )
    assert (repository / ".repo-dive/wiki.json").read_bytes() == before

    pending_page = page_by_id(repository, "overview")
    valid = write_submission(
        tmp_path,
        pending_page,
        evidence_ids=["evidence:not-yet-collected"],
    )
    assert (
        main(
            [
                *submit_arguments(repository, "overview", str(valid)),
                "--format",
                "json",
            ]
        )
        == 2
    )
    assert (
        result_document(capsys.readouterr().out)["error"]["code"]
        == "wiki_page_state_invalid"
    )
    assert (repository / ".repo-dive/wiki.json").read_bytes() == before


def test_wiki_page_rejects_unencodable_json_body_as_safe_validation_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    page = collect_evidence(repository, "overview", capsys)
    document = (
        '{"schema_version":"2.0","page_id":"overview","subsections":['
        '{"subsection_id":"runtime_flow",'
        f'"evidence_ids":["{page.evidence[0].evidence_id}"],'
        '"body":"\\ud800"}]}'
    )
    input_path = tmp_path / "surrogate.json"
    input_path.write_text(document, encoding="utf-8")

    assert (
        main(
            [
                *submit_arguments(repository, "overview", str(input_path)),
                "--format",
                "json",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert result_document(captured.out)["error"]["code"] == "wiki_page_body_invalid"
    assert "\\ud800" not in captured.out
    assert "\\ud800" not in captured.err
    assert page_by_id(repository, "overview").status is PageStatus.EVIDENCE_READY


def test_wiki_page_rejects_stale_evidence_and_changed_generated_page(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = copy_fixture(tmp_path)
    initialize_wiki(repository, tmp_path, capsys)
    page = collect_evidence(repository, "overview", capsys, max_results=1)
    input_path = write_submission(tmp_path, page)
    run_json(capsys, submit_arguments(repository, "overview", str(input_path)))
    generated = page_by_id(repository, "overview")
    changed = write_submission(
        tmp_path,
        generated,
        body="# Overview\n\nA changed generated page.\n",
        filename="changed.json",
    )

    assert (
        main(
            [
                *submit_arguments(repository, "overview", str(changed)),
                "--format",
                "json",
            ]
        )
        == 2
    )
    assert (
        result_document(capsys.readouterr().out)["error"]["code"]
        == "wiki_page_state_invalid"
    )
    assert page_by_id(repository, "overview") == generated

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
            "--max-results",
            "1",
        ],
    )
    refreshed = page_by_id(repository, "overview")
    stale_input = write_submission(tmp_path, refreshed, filename="stale.json")
    app_path = repository / "src/app.py"
    app_path.write_text(
        app_path.read_text(encoding="utf-8").replace("Hello", "Welcome"),
        encoding="utf-8",
    )
    run_json(capsys, ["index", str(repository)])

    assert (
        main(
            [
                *submit_arguments(repository, "overview", str(stale_input)),
                "--format",
                "json",
            ]
        )
        == 3
    )
    assert (
        result_document(capsys.readouterr().out)["error"]["code"]
        == "wiki_evidence_stale"
    )
    stale_page = page_by_id(repository, "overview")
    assert stale_page.status is PageStatus.EVIDENCE_READY
    assert stale_page.body == generated.body
