"""Stable domain errors and process exit codes."""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class ExitCode(IntEnum):
    """Supported process exit codes for repo-dive commands."""

    SUCCESS = 0
    INVOCATION = 2
    REPOSITORY = 3
    INTERNAL = 4


class RepoDiveError(Exception):
    """Base error carrying a stable machine code and safe details."""

    exit_code: ExitCode

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class InvocationError(RepoDiveError):
    """An invocation, option, or input-schema validation error."""

    exit_code = ExitCode.INVOCATION


class RepositoryError(RepoDiveError):
    """A repository or requested repository-data error."""

    exit_code = ExitCode.REPOSITORY


class InternalOperationError(RepoDiveError):
    """A failure after a valid operation has started."""

    exit_code = ExitCode.INTERNAL
