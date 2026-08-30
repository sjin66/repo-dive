from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from repo_dive.cli import main

FIXTURE = Path(__file__).parents[1] / "fixtures" / "index_repo"


def _run(capsys: pytest.CaptureFixture[str], arguments: list[str]) -> dict[str, Any]:
    assert main([*arguments, "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert isinstance(result, dict)
    return result


def test_classify_and_init_compose_governed_structure_without_caller_outline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE, repository, ignore=shutil.ignore_patterns(".repo-dive"))
    _run(capsys, ["index", str(repository)])

    classified = _run(capsys, ["wiki", "classify", str(repository)])
    classification = classified["result"]["classification"]
    assert classification["index_build_id"]
    assert classification["effective_primary"]["id"] == "general_mixed"

    initialized = _run(
        capsys,
        ["wiki", "init", str(repository), "--locale", "ja"],
    )
    result = initialized["result"]
    assert result["classification"]["effective_primary"]["id"] == "general_mixed"
    assert result["template"]["locale"] == "ja"
    assert result["section_count"] > 0
    assert result["page_count"] > 0
    assert result["subsection_count"] >= result["page_count"] * 2

    status = _run(capsys, ["wiki", "status", str(repository)])["result"]
    subsections = [
        subsection
        for section in status["sections"]
        for page in section["pages"]
        for subsection in page["subsections"]
    ]
    assert all(not item["id"].endswith("_subsections") for item in subsections)
    assert all(item["direct_source_paths"] for item in subsections)
    assert all(item["documentation_only"] is False for item in subsections)

    metadata = json.loads(
        (repository / ".repo-dive/metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["repository_classification"] == result["classification"]
    assert metadata["template"] == result["template"]


@pytest.mark.parametrize("locale", ("en", "zh-CN", "ja"))
def test_developer_tool_extension_page_requires_explicit_protocol_evidence(
    locale: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / f"developer-{locale}"
    shutil.copytree(FIXTURE, repository, ignore=shutil.ignore_patterns(".repo-dive"))
    (repository / "src/extensions.py").write_text(
        "\n".join(
            (
                "from typing import Protocol",
                "class ParserAdapter(Protocol):",
                "    def parse(self, file, text): ...",
                "class LocalRetriever(Protocol):",
                "    def retrieve(self, query): ...",
                "class EmbeddingProvider(Protocol):",
                "    def embed(self, texts): ...",
            )
        ),
        encoding="utf-8",
    )
    _run(capsys, ["index", str(repository)])
    _run(
        capsys,
        [
            "wiki",
            "init",
            str(repository),
            "--locale",
            locale,
            "--template",
            "developer_tool",
        ],
    )

    pages = {
        page["id"]: page
        for section in _run(capsys, ["wiki", "status", str(repository)])["result"][
            "sections"
        ]
        for page in section["pages"]
    }
    extension_page = pages["tool_extension_points_page"]
    assert [item["id"] for item in extension_page["subsections"]] == [
        "tool_extension_points_protocol_contracts",
        "tool_extension_points_implementation_workflow",
    ]
    assert all(
        item["direct_source_paths"] == ["src/extensions.py"]
        for item in extension_page["subsections"]
    )


@pytest.mark.parametrize("locale", ("en", "zh-CN", "ja"))
def test_developer_tool_omits_extension_page_for_generic_keyword_hits(
    locale: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / f"generic-{locale}"
    shutil.copytree(FIXTURE, repository, ignore=shutil.ignore_patterns(".repo-dive"))
    (repository / "src/extensions.py").write_text(
        "message = 'parser provider adapter retriever protocol extension'\n",
        encoding="utf-8",
    )
    _run(capsys, ["index", str(repository)])
    _run(
        capsys,
        [
            "wiki",
            "init",
            str(repository),
            "--locale",
            locale,
            "--template",
            "developer_tool",
        ],
    )

    page_ids = {
        page["id"]
        for section in _run(capsys, ["wiki", "status", str(repository)])["result"][
            "sections"
        ]
        for page in section["pages"]
    }
    assert "tool_extension_points_page" not in page_ids


def test_cli_extension_page_still_uses_explicit_protocol_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "cli"
    shutil.copytree(FIXTURE, repository, ignore=shutil.ignore_patterns(".repo-dive"))
    (repository / "src/extensions.py").write_text(
        "from typing import Protocol\n"
        "class ParserAdapter(Protocol):\n"
        "    def parse(self, file, text): ...\n",
        encoding="utf-8",
    )
    _run(capsys, ["index", str(repository)])
    _run(
        capsys,
        [
            "wiki",
            "init",
            str(repository),
            "--locale",
            "en",
            "--template",
            "cli_tool",
        ],
    )

    pages = {
        page["id"]: page
        for section in _run(capsys, ["wiki", "status", str(repository)])["result"][
            "sections"
        ]
        for page in section["pages"]
    }
    assert pages["cli_extension_points_page"]["subsections"][0][
        "direct_source_paths"
    ] == ["src/extensions.py"]


def test_cli_extension_page_ignores_generic_keyword_hits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "cli-generic"
    shutil.copytree(FIXTURE, repository, ignore=shutil.ignore_patterns(".repo-dive"))
    (repository / "src/extensions.py").write_text(
        "message = 'parser provider adapter retriever protocol extension'\n",
        encoding="utf-8",
    )
    _run(capsys, ["index", str(repository)])
    _run(
        capsys,
        [
            "wiki",
            "init",
            str(repository),
            "--locale",
            "en",
            "--template",
            "cli_tool",
        ],
    )

    page_ids = {
        page["id"]
        for section in _run(capsys, ["wiki", "status", str(repository)])["result"][
            "sections"
        ]
        for page in section["pages"]
    }
    assert "cli_extension_points_page" not in page_ids


def test_governed_init_rejects_caller_owned_structure_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE, repository, ignore=shutil.ignore_patterns(".repo-dive"))
    _run(capsys, ["index", str(repository)])

    exit_code = main(
        [
            "wiki",
            "init",
            str(repository),
            "--locale",
            "en",
            "--input",
            "caller-structure.json",
            "--format",
            "json",
        ]
    )

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_invocation"


@pytest.mark.parametrize("locale", ("en", "zh-CN", "ja"))
def test_template_initialized_wiki_completes_full_workflow_for_every_locale(
    locale: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / locale
    shutil.copytree(FIXTURE, repository, ignore=shutil.ignore_patterns(".repo-dive"))
    _run(capsys, ["index", str(repository)])
    _run(capsys, ["wiki", "init", str(repository), "--locale", locale])
    status = _run(capsys, ["wiki", "status", str(repository)])["result"]

    for section in status["sections"]:
        for page in section["pages"]:
            evidence = _run(
                capsys,
                [
                    "wiki",
                    "evidence",
                    str(repository),
                    "--page",
                    page["id"],
                    "--token-budget",
                    "1200",
                ],
            )["result"]
            direct_items = {
                subsection_id: item["evidence_id"]
                for item in evidence["items"]
                if item["role"] == "direct"
                for subsection_id in item["subsection_ids"]
            }
            submission = {
                "schema_version": "2.0",
                "page_id": page["id"],
                "subsections": [
                    {
                        "subsection_id": subsection["id"],
                        "body": "Grounded content.\n",
                        "evidence_ids": [direct_items[subsection["id"]]],
                    }
                    for subsection in page["subsections"]
                ],
            }
            submission_path = tmp_path / f"{locale}-{page['id']}.json"
            submission_path.write_text(json.dumps(submission), encoding="utf-8")
            _run(
                capsys,
                [
                    "wiki",
                    "page",
                    str(repository),
                    "--page",
                    page["id"],
                    "--input",
                    str(submission_path),
                ],
            )

    assert _run(capsys, ["wiki", "validate", str(repository)])["result"]["valid"]
    built = _run(capsys, ["wiki", "build", str(repository)])["result"]
    assert built["template"]["locale"] == locale
    assert (repository / ".repo-dive/wiki.md").is_file()


def test_deprecated_structure_accepts_only_legacy_input_shape(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE, repository, ignore=shutil.ignore_patterns(".repo-dive"))
    _run(capsys, ["index", str(repository)])
    structure = {
        "schema_version": "1.0",
        "title": "示例 Wiki",
        "description": "基于代码库 Evidence 的开发文档。",
        "output_language": "zh-CN",
        "sections": [
            {
                "id": "guide",
                "title": "指南",
                "pages": [
                    {
                        "id": "overview",
                        "title": "概览",
                        "description": "解释入口。",
                        "relevant_files": ["src/app.py"],
                        "related_page_ids": [],
                    }
                ],
            }
        ],
    }
    structure_path = tmp_path / "structure.json"
    structure_path.write_text(json.dumps(structure), encoding="utf-8")
    initialized = _run(
        capsys,
        ["wiki", "structure", str(repository), "--input", str(structure_path)],
    )
    assert initialized["result"]["wiki_schema_version"] == "1.0"
    assert (
        json.loads((repository / ".repo-dive/wiki.json").read_text(encoding="utf-8"))[
            "schema_version"
        ]
        == "1.0"
    )


def test_explicit_init_replaces_legacy_state_but_preserves_last_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE, repository, ignore=shutil.ignore_patterns(".repo-dive"))
    _run(capsys, ["index", str(repository)])
    artifact_root = repository / ".repo-dive"
    prior_markdown = b"# Last valid Wiki\n"
    (artifact_root / "wiki.md").write_bytes(prior_markdown)
    (artifact_root / "wiki.json").write_text(
        '{"schema_version":"1.0","legacy":true}\n', encoding="utf-8"
    )
    (artifact_root / "metadata.json").write_text(
        '{"schema_version":"1.0","wiki_schema_version":"1.0"}\n',
        encoding="utf-8",
    )
    structure = {
        "schema_version": "2.0",
        "title": "Wiki",
        "description": "Grounded documentation.",
        "output_language": "en",
        "sections": [
            {
                "id": "guide",
                "title": "Guide",
                "pages": [
                    {
                        "id": "overview",
                        "title": "Overview",
                        "description": "Explain the entrypoint.",
                        "relevant_files": ["src/app.py"],
                        "related_page_ids": [],
                        "subsections": [
                            {
                                "id": "runtime_flow",
                                "title": "Runtime flow",
                                "description": "Trace the entrypoint.",
                                "direct_source_paths": ["src/app.py"],
                                "documentation_only": False,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    structure_path = tmp_path / "structure.json"
    structure_path.write_text(json.dumps(structure), encoding="utf-8")

    first = _run(capsys, ["wiki", "init", str(repository), "--locale", "en"])
    second = _run(capsys, ["wiki", "init", str(repository), "--locale", "en"])

    assert first["result"]["changed"] is True
    assert second["result"]["changed"] is False
    assert (artifact_root / "wiki.md").read_bytes() == prior_markdown
