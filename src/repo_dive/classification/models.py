"""Immutable contracts for deterministic repository classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from repo_dive.schema import JsonObject

SelectionSource = Literal["automatic", "fallback", "override"]
Confidence = Literal["high", "fallback", "override"]
FallbackReason = Literal["below_threshold", "tied", "ambiguous"]
Dimension = Literal["primary", "topology", "facet"]

CLASSIFICATION_SCHEMA_VERSION = "1.0"
CLASSIFIER_ID = "builtin-repository-classifier"
CLASSIFIER_VERSION = "1"
TAXONOMY_VERSION = "1"
MAX_MANIFEST_BYTES = 65_536


@dataclass(frozen=True, slots=True)
class Taxon:
    """One registry-ordered taxonomy member and its selection threshold."""

    id: str
    threshold: int

    def __post_init__(self) -> None:
        if not _is_id(self.id) or self.threshold < 0:
            raise ValueError("taxon id and threshold must be valid")


@dataclass(frozen=True, slots=True)
class IndexedFile:
    """The bounded indexed-file evidence visible to the classifier."""

    path: str
    language: str
    readable: bool
    size_bytes: int = 0
    text: str | None = None

    def __post_init__(self) -> None:
        if not _is_posix_path(self.path) or not self.language or self.size_bytes < 0:
            raise ValueError("indexed file path and language must be valid")
        if not self.readable and self.text is not None:
            raise ValueError("unreadable indexed files may not carry text")


@dataclass(frozen=True, slots=True)
class IndexSnapshot:
    """Timestamp-free classifier input tied to one published index identity."""

    repository_fingerprint: str
    index_build_id: str
    files: tuple[IndexedFile, ...]

    def __post_init__(self) -> None:
        if not self.repository_fingerprint or not self.index_build_id:
            raise ValueError("index identities must not be empty")
        ordered = tuple(sorted(self.files, key=lambda item: item.path))
        paths = tuple(item.path for item in ordered)
        if len(paths) != len(set(paths)):
            raise ValueError("indexed file paths must be unique")
        object.__setattr__(self, "files", ordered)


@dataclass(frozen=True, slots=True)
class ScoredPrimary:
    id: str
    score: int
    confidence: Confidence

    def to_document(self) -> JsonObject:
        return {"confidence": self.confidence, "id": self.id, "score": self.score}


@dataclass(frozen=True, slots=True)
class ScoredTaxon:
    id: str
    score: int

    def to_document(self) -> JsonObject:
        return {"id": self.id, "score": self.score}


@dataclass(frozen=True, slots=True)
class MatchedSignal:
    id: str
    weight: int
    paths: tuple[str, ...]

    def to_document(self) -> JsonObject:
        return {"id": self.id, "paths": list(self.paths), "weight": self.weight}


@dataclass(frozen=True, slots=True)
class ClassificationObservation:
    code: Literal["manifest_malformed", "manifest_oversized"]
    path: str

    def to_document(self) -> JsonObject:
        return {"code": self.code, "path": self.path}


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    repository_fingerprint: str
    index_build_id: str
    selection_source: SelectionSource
    detected_primary: ScoredPrimary
    effective_primary: ScoredPrimary
    topology: ScoredTaxon
    facets: tuple[ScoredTaxon, ...]
    matched_signals: tuple[MatchedSignal, ...]
    observations: tuple[ClassificationObservation, ...] = ()
    template_override: str | None = None
    fallback_reason: FallbackReason | None = None
    schema_version: str = CLASSIFICATION_SCHEMA_VERSION
    classifier_id: str = CLASSIFIER_ID
    classifier_version: str = CLASSIFIER_VERSION
    taxonomy_version: str = TAXONOMY_VERSION

    def to_document(self) -> JsonObject:
        return {
            "classifier_id": self.classifier_id,
            "classifier_version": self.classifier_version,
            "detected_primary": self.detected_primary.to_document(),
            "effective_primary": self.effective_primary.to_document(),
            "facets": [item.to_document() for item in self.facets],
            "fallback_reason": self.fallback_reason,
            "index_build_id": self.index_build_id,
            "matched_signals": [item.to_document() for item in self.matched_signals],
            "observations": [item.to_document() for item in self.observations],
            "repository_fingerprint": self.repository_fingerprint,
            "schema_version": self.schema_version,
            "selection_source": self.selection_source,
            "taxonomy_version": self.taxonomy_version,
            "template_override": self.template_override,
            "topology": self.topology.to_document(),
        }


def _is_id(value: str) -> bool:
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


def _is_posix_path(value: str) -> bool:
    parts = value.split("/")
    return (
        bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in parts)
    )
