"""Strict localized copy resources for every built-in Wiki Subsection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import cast

from repo_dive.schema import JsonObject, JsonValue

COPY_SCHEMA_VERSION = "1.0"
COPY_LOCALES = ("en", "zh-CN", "ja")


@dataclass(frozen=True, slots=True)
class LocalizedSubsectionCopy:
    """Exact resource-owned title and focused purpose for one Subsection."""

    title: str
    description: str

    def __post_init__(self) -> None:
        for value in (self.title, self.description):
            if not value or value.strip() != value:
                raise ValueError("Subsection copy must be non-empty and unpadded")


@cache
def load_subsection_copy(
    locale: str,
) -> tuple[tuple[str, LocalizedSubsectionCopy], ...]:
    """Load one exact locale resource without normalization or fallback."""
    if locale not in COPY_LOCALES:
        raise ValueError("Subsection copy locale is not supported")
    resource = files("repo_dive.wiki.templates.resources").joinpath(
        locale, "subsections.json"
    )
    try:
        document = _object(
            json.loads(
                resource.read_text(encoding="utf-8"),
                object_pairs_hook=_unique_object,
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError("Subsection copy resource is invalid") from error
    if set(document) != {"locale", "schema_version", "subsections"}:
        raise ValueError("Subsection copy resource fields are invalid")
    if (
        document["locale"] != locale
        or document["schema_version"] != COPY_SCHEMA_VERSION
    ):
        raise ValueError("Subsection copy resource identity is invalid")
    subsection_values = _object(document["subsections"])
    entries: list[tuple[str, LocalizedSubsectionCopy]] = []
    for logical_id, value in subsection_values.items():
        if not _logical_id(logical_id):
            raise ValueError("Subsection copy ID is invalid")
        item = _object(value)
        if set(item) != {"description", "title"}:
            raise ValueError("Subsection copy entry fields are invalid")
        entries.append(
            (
                logical_id,
                LocalizedSubsectionCopy(
                    title=_string(item["title"]),
                    description=_string(item["description"]),
                ),
            )
        )
    result = tuple(sorted(entries))
    descriptions = tuple(item.description for _, item in result)
    if len(descriptions) != len(set(descriptions)):
        raise ValueError("Subsection descriptions must be unique within a locale")
    return result


def _object(value: JsonValue | object) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("Subsection copy value must be an object")
    return cast(JsonObject, value)


def _string(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise TypeError("Subsection copy value must be a string")
    return value


def _logical_id(value: str) -> bool:
    return (
        bool(value)
        and value[0].isascii()
        and value[0].islower()
        and all(
            character.isascii()
            and (character.islower() or character.isdigit() or character == "_")
            for character in value
        )
    )


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Subsection copy resource contains duplicate keys")
        result[key] = value
    return result


__all__ = [
    "COPY_LOCALES",
    "COPY_SCHEMA_VERSION",
    "LocalizedSubsectionCopy",
    "load_subsection_copy",
]
