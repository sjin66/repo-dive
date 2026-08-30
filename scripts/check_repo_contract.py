"""Validate repository-level agent and documentation contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

REQUIRED_ROOT_FILES = ("AGENTS.md", "README.md", "README.zh-CN.md")
COMPATIBILITY_FILES = (
    Path(".github/copilot-instructions.md"),
    Path("CLAUDE.md"),
    Path("GEMINI.md"),
)
MAX_COMPATIBILITY_LINES = 20
CLI_CONTRACT_PATHS = (
    Path("docs/en/cli-contract.md"),
    Path("docs/zh-CN/cli-contract.md"),
)
TECHNICAL_DOCUMENTS = {
    "architecture.md": {
        "literals": (
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
        ),
        "sections": ("packages", "index-storage", "rag-boundary"),
    },
    "wiki-workflow.md": {
        "literals": (
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
        ),
        "sections": ("commands", "page-state", "single-page-recovery"),
    },
}
CONTRACT_EXAMPLE_MARKERS = (
    "index-success",
    "search-success",
    "context-success",
    "wiki-success",
    "error",
    "stdin",
    "recovery",
)
AGENT_WORKFLOW_LITERALS = (
    "repo-dive index",
    "repo-dive wiki classify",
    "repo-dive wiki init",
    "repo-dive wiki evidence",
    "repo-dive wiki page",
    "repo-dive wiki build",
    "--input -",
    "MCP is not required",
)
JSON_FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
TECHNICAL_FENCE = re.compile(
    r"```(bash|json|markdown|text)\s*\n(.*?)\n```",
    re.DOTALL,
)
README_COMMAND_PREFIXES = (
    ".venv/bin/python -m repo_dive.evaluation.runner",
    ".venv/bin/repo-dive",
    "make ",
)
SUPPORTED_PYTHONS = ("3.11", "3.12", "3.13")
REQUIRED_MAKE_TARGETS = ("setup", "check", "test-all", "package", "package-smoke")
REQUIRED_CI_MAKE_COMMANDS = (
    "make setup",
    "make check",
    "make test-all",
    "make package-smoke",
)
DEVELOPMENT_LITERALS = (
    "Python 3.11",
    "Python 3.12",
    "Python 3.13",
    "make package",
    "make package-smoke",
    ".[vector]",
    "local_files_only=True",
)
CI_RUN_COMMAND = re.compile(r"^\s*(?:-\s*)?run:\s*(.+?)\s*$", re.MULTILINE)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def validate_repository_contract(root: Path) -> list[str]:
    """Return stable validation errors for the repository rooted at ``root``."""
    root = root.resolve()
    errors: list[str] = []

    for filename in REQUIRED_ROOT_FILES:
        if not (root / filename).is_file():
            errors.append(f"{filename} is missing")

    agents_path = root / "AGENTS.md"
    if agents_path.is_file():
        agents_content = agents_path.read_text(encoding="utf-8")
        for literal in AGENT_WORKFLOW_LITERALS:
            if literal not in agents_content:
                errors.append(
                    f"AGENTS.md is missing required agent workflow literal: {literal}"
                )

    english_dir = root / "docs/en"
    chinese_dir = root / "docs/zh-CN"
    english_files = {path.name for path in english_dir.glob("*.md") if path.is_file()}
    chinese_files = {path.name for path in chinese_dir.glob("*.md") if path.is_file()}

    for filename in sorted(english_files - chinese_files):
        errors.append(f"docs/zh-CN/{filename} is missing for docs/en/{filename}")
    for filename in sorted(chinese_files - english_files):
        errors.append(f"docs/en/{filename} is missing for docs/zh-CN/{filename}")

    for language in ("en", "zh-CN"):
        relative_path = Path("docs") / language / "development.md"
        path = root / relative_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for literal in DEVELOPMENT_LITERALS:
            if literal not in content:
                errors.append(
                    f"{relative_path.as_posix()} is missing required release "
                    f"literal: {literal}"
                )

    for language in ("en", "zh-CN"):
        for filename, requirements in TECHNICAL_DOCUMENTS.items():
            relative_path = Path("docs") / language / filename
            path = root / relative_path
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8")
            for literal in requirements["literals"]:
                if literal not in content:
                    errors.append(
                        f"{relative_path.as_posix()} is missing required technical "
                        f"literal: {literal}"
                    )
            for marker in requirements["sections"]:
                if f"<!-- contract-section:{marker} -->" not in content:
                    errors.append(
                        f"{relative_path.as_posix()} is missing contract section "
                        f"marker: {marker}"
                    )

    for relative_path in CLI_CONTRACT_PATHS:
        path = root / relative_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for marker in CONTRACT_EXAMPLE_MARKERS:
            if f"<!-- contract-example:{marker} -->" not in content:
                errors.append(
                    f"{relative_path.as_posix()} is missing contract example marker: "
                    f"{marker}"
                )
        for index, example in enumerate(JSON_FENCE.findall(content), start=1):
            try:
                json.loads(example)
            except json.JSONDecodeError:
                errors.append(
                    f"{relative_path.as_posix()} contains invalid JSON example {index}"
                )

    english_contract = root / CLI_CONTRACT_PATHS[0]
    chinese_contract = root / CLI_CONTRACT_PATHS[1]
    if english_contract.is_file() and chinese_contract.is_file():
        english_blocks = TECHNICAL_FENCE.findall(
            english_contract.read_text(encoding="utf-8")
        )
        chinese_blocks = TECHNICAL_FENCE.findall(
            chinese_contract.read_text(encoding="utf-8")
        )
        if english_blocks != chinese_blocks:
            errors.append("bilingual CLI contract technical fenced blocks differ")

    english_readme = root / "README.md"
    chinese_readme = root / "README.zh-CN.md"
    if english_readme.is_file() and chinese_readme.is_file():
        command_lines = []
        for path in (english_readme, chinese_readme):
            command_lines.append(
                tuple(
                    line.strip()
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip().startswith(README_COMMAND_PREFIXES)
                )
            )
        if command_lines[0] != command_lines[1]:
            errors.append("bilingual README CLI command lines differ")

    pyproject_path = root / "pyproject.toml"
    if pyproject_path.is_file():
        configuration = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = configuration.get("project", {})
        dependencies = project.get("dependencies", [])
        optional = project.get("optional-dependencies", {})
        if "sentence-transformers" in {_dependency_name(item) for item in dependencies}:
            errors.append(
                "pyproject.toml default dependencies must not include "
                "sentence-transformers"
            )
        if "build" not in {_dependency_name(item) for item in optional.get("dev", [])}:
            errors.append("pyproject.toml dev extra must include build")
        ruff_exclude = (
            configuration.get("tool", {}).get("ruff", {}).get("extend-exclude", [])
        )
        if ruff_exclude != [".trellis"]:
            errors.append(
                'pyproject.toml Ruff extend-exclude must be exactly [".trellis"]'
            )

    makefile_path = root / "Makefile"
    if makefile_path.is_file():
        makefile = makefile_path.read_text(encoding="utf-8")
        for target in REQUIRED_MAKE_TARGETS:
            if re.search(rf"(?m)^{re.escape(target)}(?:\s+[^:]*)?:", makefile) is None:
                errors.append(f"Makefile is missing required target: {target}")

    workflow_path = root / ".github/workflows/ci.yml"
    if workflow_path.is_file():
        workflow = workflow_path.read_text(encoding="utf-8")
        for version in SUPPORTED_PYTHONS:
            if f'"{version}"' not in workflow and f"'{version}'" not in workflow:
                errors.append(
                    f".github/workflows/ci.yml is missing Python version: {version}"
                )
        run_commands = CI_RUN_COMMAND.findall(workflow)
        for command in run_commands:
            if not command.startswith("make "):
                errors.append(
                    ".github/workflows/ci.yml must invoke verification through "
                    f"shared Make targets: {command}"
                )
        for command in REQUIRED_CI_MAKE_COMMANDS:
            if command not in run_commands:
                errors.append(
                    f".github/workflows/ci.yml is missing shared command: {command}"
                )

    for relative_path in COMPATIBILITY_FILES:
        path = root / relative_path
        display_path = _relative(path, root)
        if not path.is_file():
            errors.append(f"{display_path} is missing")
            continue

        content = path.read_text(encoding="utf-8")
        if "AGENTS.md" not in content:
            errors.append(f"{display_path} must reference AGENTS.md")
        non_empty_lines = [line for line in content.splitlines() if line.strip()]
        if len(non_empty_lines) > MAX_COMPATIBILITY_LINES:
            errors.append(
                f"{display_path} exceeds {MAX_COMPATIBILITY_LINES} non-empty lines"
            )

    return errors


def _dependency_name(requirement: object) -> str:
    if not isinstance(requirement, str):
        return ""
    return re.split(r"[<>=!~;\s\[]", requirement, maxsplit=1)[0].lower()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root to validate (default: current directory)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors = validate_repository_contract(args.root)
    if errors:
        for error in errors:
            print(f"contract error: {error}", file=sys.stderr)
        return 1
    print("Repository contracts OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
