"""Typed command contracts used by the process-level CLI."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from repo_dive.schema import JsonValue

OutputFormat = Literal["json", "markdown"]
ConfigureParser = Callable[[argparse.ArgumentParser], None]


@dataclass(frozen=True, slots=True)
class CommandOutput:
    """A complete command result awaiting process serialization."""

    command: str
    format: OutputFormat
    result: JsonValue | str
    repository: str | None = None
    warnings: tuple[str, ...] = ()


CommandHandler = Callable[[argparse.Namespace], CommandOutput]


@dataclass(frozen=True, slots=True)
class Command:
    """One CLI subcommand and its argument/handler boundary."""

    name: str
    help: str
    configure: ConfigureParser
    handler: CommandHandler
