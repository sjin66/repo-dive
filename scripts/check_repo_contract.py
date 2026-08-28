"""Validate repository-level agent and documentation contracts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REQUIRED_ROOT_FILES = ("AGENTS.md", "README.md", "README.zh-CN.md")
COMPATIBILITY_FILES = (
    Path(".github/copilot-instructions.md"),
    Path("CLAUDE.md"),
    Path("GEMINI.md"),
)
MAX_COMPATIBILITY_LINES = 20


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def validate_repository_contract(root: Path) -> list[str]:
    """Return stable validation errors for the repository rooted at ``root``."""
    root = root.resolve()
    errors: list[str] = []

    for filename in REQUIRED_ROOT_FILES:
        if not (root / filename).is_file():
            errors.append(f"{filename} is missing")

    english_dir = root / "docs/en"
    chinese_dir = root / "docs/zh-CN"
    english_files = {path.name for path in english_dir.glob("*.md") if path.is_file()}
    chinese_files = {path.name for path in chinese_dir.glob("*.md") if path.is_file()}

    for filename in sorted(english_files - chinese_files):
        errors.append(f"docs/zh-CN/{filename} is missing for docs/en/{filename}")
    for filename in sorted(chinese_files - english_files):
        errors.append(f"docs/en/{filename} is missing for docs/zh-CN/{filename}")

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
