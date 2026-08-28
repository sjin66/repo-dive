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
    "repo-dive wiki structure",
    "repo-dive wiki evidence",
    "repo-dive wiki page",
    "repo-dive wiki build",
    "--input -",
    "MCP is not required",
)


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
        _write(root / "docs/en" / filename, content)
        _write(root / "docs/zh-CN" / filename, content)

    for filename in ("CLAUDE.md", "GEMINI.md"):
        _write(root / filename, "Follow @AGENTS.md.\n")
    _write(
        root / ".github/copilot-instructions.md",
        "Follow @../AGENTS.md.\n",
    )


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
