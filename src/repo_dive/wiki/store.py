"""Atomic repository-owned persistence for public Wiki JSON artifacts."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar, cast

from repo_dive.errors import RepositoryError
from repo_dive.schema import JsonObject
from repo_dive.storage.atomic import atomic_write_json
from repo_dive.storage.paths import resolve_repository, resolve_within_repository
from repo_dive.wiki.models import (
    METADATA_SCHEMA_VERSION,
    WIKI_SCHEMA_VERSION,
    Metadata,
    Wiki,
    metadata_from_document,
    wiki_from_document,
)

WIKI_PATH = ".repo-dive/wiki.json"
METADATA_PATH = ".repo-dive/metadata.json"

ArtifactT = TypeVar("ArtifactT")


class WikiStore:
    """Read and atomically replace strict public Wiki state files."""

    def __init__(self, repository: str | Path) -> None:
        self.repository = resolve_repository(repository)

    def has_wiki(self) -> bool:
        """Return whether a Wiki state path currently exists."""
        return self._exists(WIKI_PATH)

    def has_metadata(self) -> bool:
        """Return whether a Wiki metadata path currently exists."""
        return self._exists(METADATA_PATH)

    def read_wiki(self) -> Wiki:
        """Read Wiki state without repairing or rewriting invalid bytes."""
        return self._read(
            WIKI_PATH,
            expected_version=WIKI_SCHEMA_VERSION,
            invalid_code="wiki_state_invalid",
            version_code="wiki_state_version_unsupported",
            invalid_message="Repository Wiki state is invalid.",
            version_message="Repository Wiki state version is not supported.",
            decoder=wiki_from_document,
        )

    def read_metadata(self) -> Metadata:
        """Read Wiki metadata without repairing or rewriting invalid bytes."""
        return self._read(
            METADATA_PATH,
            expected_version=METADATA_SCHEMA_VERSION,
            invalid_code="wiki_metadata_invalid",
            version_code="wiki_metadata_version_unsupported",
            invalid_message="Repository Wiki metadata is invalid.",
            version_message="Repository Wiki metadata version is not supported.",
            decoder=metadata_from_document,
        )

    def write_wiki(self, wiki: Wiki) -> Path:
        """Atomically replace the complete public Wiki state document."""
        return atomic_write_json(self.repository, WIKI_PATH, wiki.to_document())

    def write_metadata(self, metadata: Metadata) -> Path:
        """Atomically replace the complete public Wiki metadata document."""
        return atomic_write_json(
            self.repository,
            METADATA_PATH,
            metadata.to_document(),
        )

    def _read(
        self,
        relative_path: str,
        *,
        expected_version: str,
        invalid_code: str,
        version_code: str,
        invalid_message: str,
        version_message: str,
        decoder: Callable[[JsonObject], ArtifactT],
    ) -> ArtifactT:
        path = resolve_within_repository(
            self.repository,
            relative_path,
            must_exist=True,
        )
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RepositoryError(invalid_code, invalid_message) from error

        if isinstance(value, dict):
            actual_version = value.get("schema_version")
            if isinstance(actual_version, str) and actual_version != expected_version:
                raise RepositoryError(
                    version_code,
                    version_message,
                    details={"actual": actual_version, "expected": expected_version},
                )
        try:
            document = _object(value)
            return decoder(document)
        except (KeyError, TypeError, ValueError) as error:
            raise RepositoryError(invalid_code, invalid_message) from error

    def _exists(self, relative_path: str) -> bool:
        path = resolve_within_repository(self.repository, relative_path)
        return path.exists()


def _object(value: object) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("value must be an object")
    return cast(JsonObject, value)


__all__ = ["METADATA_PATH", "WIKI_PATH", "WikiStore"]
