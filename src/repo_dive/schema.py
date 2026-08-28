"""Versioned JSON result contracts shared by CLI commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

SCHEMA_VERSION = "1.0"

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]

ResultT = TypeVar("ResultT", bound=JsonValue)


@dataclass(frozen=True, slots=True)
class ErrorBody:
    """Stable machine-readable error data."""

    code: str
    message: str
    details: JsonObject | None = None

    def to_document(self) -> JsonObject:
        """Return the JSON-compatible error object."""
        document: JsonObject = {"code": self.code, "message": self.message}
        if self.details is not None:
            document["details"] = self.details
        return document


@dataclass(frozen=True, slots=True)
class ResultEnvelope(Generic[ResultT]):
    """Successful command result envelope."""

    command: str
    result: ResultT
    repository: str | None = None
    warnings: tuple[str, ...] = ()

    def to_document(self) -> JsonObject:
        """Return the versioned JSON-compatible result document."""
        document: JsonObject = {
            "schema_version": SCHEMA_VERSION,
            "command": self.command,
            "result": self.result,
            "warnings": list(self.warnings),
        }
        if self.repository is not None:
            document["repository"] = self.repository
        return document


@dataclass(frozen=True, slots=True)
class ErrorEnvelope:
    """Failed command result envelope."""

    command: str
    error: ErrorBody
    repository: str | None = None

    def to_document(self) -> JsonObject:
        """Return the versioned JSON-compatible error document."""
        document: JsonObject = {
            "schema_version": SCHEMA_VERSION,
            "command": self.command,
            "error": self.error.to_document(),
        }
        if self.repository is not None:
            document["repository"] = self.repository
        return document


def serialize_json_document(value: object) -> str:
    """Serialize a complete stable UTF-8 JSON document with one newline."""
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
