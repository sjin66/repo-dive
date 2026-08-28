from pathlib import Path

from scripts.check_repo_contract import validate_repository_contract

DOC_NAMES = (
    "architecture.md",
    "cli-contract.md",
    "wiki-workflow.md",
    "development.md",
)


def _write(path: Path, content: str = "# Contract\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_valid_contract(root: Path) -> None:
    for filename in ("AGENTS.md", "README.md", "README.zh-CN.md"):
        _write(root / filename)

    for filename in DOC_NAMES:
        _write(root / "docs/en" / filename)
        _write(root / "docs/zh-CN" / filename)

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
