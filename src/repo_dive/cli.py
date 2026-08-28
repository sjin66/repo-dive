"""Process-level command-line interface for repo-dive."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import NoReturn

from repo_dive import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the root parser without performing process I/O."""
    parser = argparse.ArgumentParser(
        prog="repo-dive",
        description="Collect local repository evidence for coding agents.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="print the installed repo-dive version and exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI for an explicit argument sequence."""
    args = build_parser().parse_args(argv)
    if args.version:
        print(f"repo-dive {__version__}")
    return 0


def entrypoint() -> NoReturn:
    """Translate the testable return code into a console-script exit."""
    raise SystemExit(main())
