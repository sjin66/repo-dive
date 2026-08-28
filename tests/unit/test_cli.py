import argparse

import pytest

from repo_dive import __version__
from repo_dive.cli import main
from repo_dive.commands import Command, CommandOutput


def test_version_prints_stable_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"repo-dive {__version__}"


def test_help_describes_agent_friendly_cli(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "local repository evidence" in capsys.readouterr().out


def test_command_handler_is_dispatched_and_serialized_as_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def configure(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--format", choices=("json",), required=True)

    def handle(args: argparse.Namespace) -> CommandOutput:
        assert args.format == "json"
        return CommandOutput(
            command="inspect",
            format="json",
            result={"status": "ok"},
            repository="/tmp/example",
        )

    command = Command(
        name="inspect",
        help="inspect a repository",
        configure=configure,
        handler=handle,
    )

    assert main(["inspect", "--format", "json"], commands=(command,)) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.endswith("\n")
    assert '"command":"inspect"' in captured.out
    assert '"result":{"status":"ok"}' in captured.out


def test_unexpected_handler_error_returns_safe_internal_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def configure(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--format", choices=("json",), required=True)

    def handle(args: argparse.Namespace) -> CommandOutput:
        raise RuntimeError("private implementation detail")

    command = Command(
        name="inspect",
        help="inspect a repository",
        configure=configure,
        handler=handle,
    )

    assert main(["inspect", "--format", "json"], commands=(command,)) == 4
    captured = capsys.readouterr()
    assert "private implementation detail" not in captured.out
    assert "private implementation detail" not in captured.err
    assert '"code":"internal_operation_failed"' in captured.out
    assert "The operation failed unexpectedly." in captured.err
