from pathlib import Path

from scripts.check_repo_contract import validate_repository_contract

DOC_NAMES = (
    "architecture.md",
    "cli-contract.md",
    "wiki-workflow.md",
    "development.md",
)

EXAMPLE_MARKERS = (
    "index-success",
    "search-success",
    "context-success",
    "wiki-success",
    "error",
    "stdin",
    "recovery",
)

AGENT_WORKFLOW = (
    "repo-dive index",
    "repo-dive wiki classify",
    "repo-dive wiki init",
    "repo-dive wiki evidence",
    "repo-dive wiki page",
    "repo-dive wiki build",
    "--input -",
    "MCP is not required",
)

ARCHITECTURE_LITERALS = (
    "commands/",
    "providers/",
    "storage/",
    "evaluation/",
    ".repo-dive/index-generations/<build-id>/index.sqlite3",
    ".repo-dive/index -> index-generations/<build-id>",
    "PRAGMA user_version = 4",
    "weighted_rrf",
    "strict",
    "degraded",
)

WIKI_WORKFLOW_LITERALS = (
    "structure -> evidence -> page -> build -> status",
    "pending -> evidence_ready",
    "evidence_ready -> generated",
    "evidence_ready -> failed",
    "evidence_ready -> pending",
    "generated -> failed",
    "generated -> pending",
    "failed -> pending",
    "collect_evidence",
    "generate_page",
    "complete",
    "retry",
    "wiki_evidence_stale",
    ".repo-dive/wiki.json",
    ".repo-dive/metadata.json",
    ".repo-dive/wiki.md",
)

DOCUMENT_SECTION_MARKERS = {
    "architecture.md": ("packages", "index-storage", "rag-boundary"),
    "wiki-workflow.md": ("commands", "page-state", "single-page-recovery"),
}

DEVELOPMENT_LITERALS = (
    "Python 3.11",
    "Python 3.12",
    "Python 3.13",
    "make package",
    "make package-smoke",
    ".[vector]",
    "local_files_only=True",
)

VALID_PYPROJECT = """\
[project]
dependencies = ["tree-sitter>=0.25"]

[project.optional-dependencies]
vector = ["sentence-transformers>=6.0"]
dev = ["build>=1.2", "pytest>=8.3"]
"""

VALID_MAKEFILE = """\
setup:\n\tpython -m pip install -e \".[dev]\"\n
check:\n\tpython scripts/check_repo_contract.py\n
test-all:\n\tpython -m pytest -q\n
package:\n\tpython -m build --wheel --sdist\n
package-smoke: package\n\tpython scripts/package_smoke.py\n
"""

VALID_CI = """\
jobs:
  verify:
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - run: make setup
      - run: make check
      - run: make test-all
      - run: make package-smoke
"""


def _write(path: Path, content: str = "# Contract\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_valid_contract(root: Path) -> None:
    _write(root / "AGENTS.md", "\n".join(AGENT_WORKFLOW) + "\n")
    for filename in ("README.md", "README.zh-CN.md"):
        _write(root / filename)

    for filename in DOC_NAMES:
        content = "# Contract\n"
        if filename == "cli-contract.md":
            content += "\n".join(
                f"<!-- contract-example:{marker} -->" for marker in EXAMPLE_MARKERS
            )
            content += '\n```json\n{"schema_version":"1.0"}\n```\n'
        elif filename == "architecture.md":
            content += "\n".join(ARCHITECTURE_LITERALS) + "\n"
        elif filename == "wiki-workflow.md":
            content += "\n".join(WIKI_WORKFLOW_LITERALS) + "\n"
        elif filename == "development.md":
            content += "\n".join(DEVELOPMENT_LITERALS) + "\n"
        if filename in DOCUMENT_SECTION_MARKERS:
            content += "\n".join(
                f"<!-- contract-section:{marker} -->"
                for marker in DOCUMENT_SECTION_MARKERS[filename]
            )
            content += "\n"
        _write(root / "docs/en" / filename, content)
        _write(root / "docs/zh-CN" / filename, content)

    for filename in ("CLAUDE.md", "GEMINI.md"):
        _write(root / filename, "Follow @AGENTS.md.\n")
    _write(
        root / ".github/copilot-instructions.md",
        "Follow @../AGENTS.md.\n",
    )
    _write(root / "pyproject.toml", VALID_PYPROJECT)
    _write(root / "Makefile", VALID_MAKEFILE)
    _write(root / ".github/workflows/ci.yml", VALID_CI)


def test_valid_repository_contract_has_no_errors(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)

    assert validate_repository_contract(tmp_path) == []


def test_missing_translation_is_reported(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    (tmp_path / "docs/zh-CN/architecture.md").unlink()

    assert validate_repository_contract(tmp_path) == [
        "docs/zh-CN/architecture.md is missing for docs/en/architecture.md"
    ]


def test_compatibility_file_must_reference_authority(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    _write(tmp_path / "CLAUDE.md", "Use independent instructions.\n")

    assert validate_repository_contract(tmp_path) == [
        "CLAUDE.md must reference AGENTS.md"
    ]


def test_cli_contract_requires_every_agent_example_marker(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    contract = tmp_path / "docs/en/cli-contract.md"
    contract.write_text(
        contract.read_text(encoding="utf-8").replace(
            "<!-- contract-example:context-success -->",
            "",
        ),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "docs/en/cli-contract.md is missing contract example marker: context-success"
    ]


def test_cli_contract_rejects_invalid_json_example(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    contract = tmp_path / "docs/zh-CN/cli-contract.md"
    contract.write_text(
        contract.read_text(encoding="utf-8").replace(
            '{"schema_version":"1.0"}',
            '{"schema_version":broken}',
        ),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "docs/zh-CN/cli-contract.md contains invalid JSON example 1",
        "bilingual CLI contract technical fenced blocks differ",
    ]


def test_agent_guide_requires_complete_cli_workflow(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8").replace("repo-dive wiki evidence", ""),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "AGENTS.md is missing required agent workflow literal: repo-dive wiki evidence"
    ]


def test_bilingual_cli_contract_requires_identical_technical_blocks(
    tmp_path: Path,
) -> None:
    _create_valid_contract(tmp_path)
    contract = tmp_path / "docs/zh-CN/cli-contract.md"
    contract.write_text(
        contract.read_text(encoding="utf-8").replace(
            '"schema_version"',
            '"schemaVersion"',
        ),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "bilingual CLI contract technical fenced blocks differ"
    ]


def test_bilingual_readmes_require_identical_cli_command_lines(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    readme = tmp_path / "README.zh-CN.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n.venv/bin/repo-dive context /repo query --token-budget 1200\n",
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "bilingual README CLI command lines differ"
    ]


def test_architecture_requires_runtime_package_and_index_contracts(
    tmp_path: Path,
) -> None:
    _create_valid_contract(tmp_path)
    architecture = tmp_path / "docs/en/architecture.md"
    architecture.write_text(
        architecture.read_text(encoding="utf-8").replace(
            ".repo-dive/index -> index-generations/<build-id>",
            "",
        ),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "docs/en/architecture.md is missing required technical literal: "
        ".repo-dive/index -> index-generations/<build-id>"
    ]


def test_wiki_workflow_requires_page_recovery_contract(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    workflow = tmp_path / "docs/zh-CN/wiki-workflow.md"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "failed -> pending",
            "",
        ),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "docs/zh-CN/wiki-workflow.md is missing required technical literal: "
        "failed -> pending"
    ]


def test_architecture_and_wiki_docs_require_shared_section_markers(
    tmp_path: Path,
) -> None:
    _create_valid_contract(tmp_path)
    workflow = tmp_path / "docs/en/wiki-workflow.md"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "<!-- contract-section:single-page-recovery -->",
            "",
        ),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "docs/en/wiki-workflow.md is missing contract section marker: "
        "single-page-recovery"
    ]


def test_ci_requires_python_311_through_313_matrix(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    workflow = tmp_path / ".github/workflows/ci.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(', "3.13"', ""),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        ".github/workflows/ci.yml is missing Python version: 3.13"
    ]


def test_ci_rejects_tool_commands_outside_shared_make_targets(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    workflow = tmp_path / ".github/workflows/ci.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8") + "      - run: python -m pytest -q\n",
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        ".github/workflows/ci.yml must invoke verification through shared Make "
        "targets: python -m pytest -q"
    ]


def test_default_dependencies_must_not_include_vector_provider(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'dependencies = ["tree-sitter>=0.25"]',
            'dependencies = ["tree-sitter>=0.25", "sentence-transformers>=6.0"]',
        ),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "pyproject.toml default dependencies must not include sentence-transformers"
    ]


def test_development_extra_must_include_package_builder(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace('"build>=1.2", ', ""),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "pyproject.toml dev extra must include build"
    ]


def test_release_harness_requires_package_smoke_make_target(tmp_path: Path) -> None:
    _create_valid_contract(tmp_path)
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        makefile.read_text(encoding="utf-8").replace("package-smoke: package", ""),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "Makefile is missing required target: package-smoke"
    ]


def test_development_docs_require_release_commands_and_supported_pythons(
    tmp_path: Path,
) -> None:
    _create_valid_contract(tmp_path)
    development = tmp_path / "docs/zh-CN/development.md"
    development.write_text(
        development.read_text(encoding="utf-8").replace("make package-smoke", ""),
        encoding="utf-8",
    )

    assert validate_repository_contract(tmp_path) == [
        "docs/zh-CN/development.md is missing required release literal: "
        "make package-smoke"
    ]
