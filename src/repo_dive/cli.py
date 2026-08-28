"""Process-level command-line interface for repo-dive."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import NoReturn

from repo_dive import __version__
from repo_dive.commands import Command, CommandOutput
from repo_dive.commands.context import CONTEXT_COMMAND
from repo_dive.commands.index import INDEX_COMMAND
from repo_dive.commands.search import SEARCH_COMMAND
from repo_dive.errors import (
    ExitCode,
    InternalOperationError,
    InvocationError,
    RepoDiveError,
)
from repo_dive.schema import (
    ErrorBody,
    ErrorEnvelope,
    ResultEnvelope,
    serialize_json_document,
)

COMMANDS: tuple[Command, ...] = (INDEX_COMMAND, SEARCH_COMMAND, CONTEXT_COMMAND)


class RepoDiveArgumentParser(argparse.ArgumentParser):
    """Translate argparse validation failures into stable domain errors."""

    def error(self, message: str) -> NoReturn:
        raise InvocationError("invalid_invocation", message)


def build_parser(commands: Sequence[Command] = COMMANDS) -> argparse.ArgumentParser:
    """Build the root parser without performing process I/O."""
    parser = RepoDiveArgumentParser(
        prog="repo-dive",
        description="Collect local repository evidence for coding agents.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="print the installed repo-dive version and exit",
    )
    if commands:
        subparsers = parser.add_subparsers(dest="command")
        for command in commands:
            subparser = subparsers.add_parser(command.name, help=command.help)
            command.configure(subparser)
            subparser.set_defaults(_handler=command.handler)
    return parser


def _requested_json(argv: Sequence[str]) -> bool:
    return any(
        argument == "--format=json"
        or (
            argument == "--format"
            and index + 1 < len(argv)
            and argv[index + 1] == "json"
        )
        for index, argument in enumerate(argv)
    )


def _command_name(argv: Sequence[str]) -> str:
    for argument in argv:
        if not argument.startswith("-"):
            return argument
    return "repo-dive"


def _validate_command_name(argv: Sequence[str], commands: Sequence[Command]) -> None:
    command_name = _command_name(argv)
    if command_name == "repo-dive" or command_name in {
        command.name for command in commands
    }:
        return
    raise InvocationError(
        "invalid_invocation",
        f"unrecognized arguments: {' '.join(argv)}",
    )


def _write_diagnostic(message: str) -> None:
    sys.stderr.write(message.rstrip("\n") + "\n")


def _emit_success(output: CommandOutput) -> None:
    if output.format == "markdown":
        if not isinstance(output.result, str):
            raise TypeError("Markdown command output must be a string.")
        sys.stdout.write(output.result)
        return

    envelope = ResultEnvelope(
        command=output.command,
        repository=output.repository,
        result=output.result,
        warnings=output.warnings,
    )
    sys.stdout.write(serialize_json_document(envelope.to_document()))


def _emit_error(command: str, error: RepoDiveError, *, json_mode: bool) -> None:
    if json_mode:
        envelope = ErrorEnvelope(
            command=command,
            error=ErrorBody(
                code=error.code,
                message=error.message,
                details=error.details,
            ),
        )
        sys.stdout.write(serialize_json_document(envelope.to_document()))
    _write_diagnostic(error.message)


def main(
    argv: Sequence[str] | None = None,
    *,
    commands: Sequence[Command] = COMMANDS,
) -> int:
    """Run the CLI for an explicit argument sequence."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    command_name = _command_name(arguments)
    json_mode = _requested_json(arguments)
    try:
        _validate_command_name(arguments, commands)
        args = build_parser(commands).parse_args(arguments)
        if args.version:
            print(f"repo-dive {__version__}")
            return ExitCode.SUCCESS

        handler = getattr(args, "_handler", None)
        if handler is None:
            return ExitCode.SUCCESS

        output = handler(args)
        _emit_success(output)
        return ExitCode.SUCCESS
    except RepoDiveError as error:
        _emit_error(command_name, error, json_mode=json_mode)
        return error.exit_code
    except Exception:
        internal_error = InternalOperationError(
            "internal_operation_failed",
            "The operation failed unexpectedly.",
        )
        _emit_error(command_name, internal_error, json_mode=json_mode)
        return internal_error.exit_code


def entrypoint() -> NoReturn:
    """Translate the testable return code into a console-script exit."""
    raise SystemExit(main())
