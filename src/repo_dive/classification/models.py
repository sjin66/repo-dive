"""Immutable contracts for deterministic repository classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from repo_dive.schema import JsonObject, JsonValue

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

    def __post_init__(self) -> None:
        if (
            not _is_id(self.id)
            or self.score < 0
            or self.confidence
            not in {
                "high",
                "fallback",
                "override",
            }
        ):
            raise ValueError("scored primary is invalid")

    def to_document(self) -> JsonObject:
        return {"confidence": self.confidence, "id": self.id, "score": self.score}


@dataclass(frozen=True, slots=True)
class ScoredTaxon:
    id: str
    score: int

    def __post_init__(self) -> None:
        if not _is_id(self.id) or self.score < 0:
            raise ValueError("scored taxon is invalid")

    def to_document(self) -> JsonObject:
        return {"id": self.id, "score": self.score}


@dataclass(frozen=True, slots=True)
class MatchedSignal:
    id: str
    weight: int
    paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not _is_id(self.id)
            or self.weight <= 0
            or not self.paths
            or len(self.paths) != len(set(self.paths))
            or any(not _is_posix_path(path) for path in self.paths)
        ):
            raise ValueError("matched classification signal is invalid")

    def to_document(self) -> JsonObject:
        return {"id": self.id, "paths": list(self.paths), "weight": self.weight}


@dataclass(frozen=True, slots=True)
class ClassificationObservation:
    code: Literal["manifest_malformed", "manifest_oversized"]
    path: str

    def __post_init__(self) -> None:
        if not _is_posix_path(self.path):
            raise ValueError("classification observation path is invalid")

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

    def __post_init__(self) -> None:
        if (
            self.schema_version != CLASSIFICATION_SCHEMA_VERSION
            or self.classifier_id != CLASSIFIER_ID
            or self.classifier_version != CLASSIFIER_VERSION
            or self.taxonomy_version != TAXONOMY_VERSION
            or not self.repository_fingerprint
            or not self.index_build_id
        ):
            raise ValueError("classification identity is unsupported")
        facet_ids = tuple(item.id for item in self.facets)
        if len(facet_ids) != len(set(facet_ids)):
            raise ValueError("classification facets must be unique")
        if self.selection_source == "override":
            if (
                self.template_override is None
                or self.effective_primary.id != self.template_override
                or self.effective_primary.confidence != "override"
            ):
                raise ValueError("classification override is inconsistent")
        elif self.template_override is not None:
            raise ValueError("automatic classification cannot retain an override")
        elif self.selection_source == "fallback":
            if (
                self.fallback_reason is None
                or self.effective_primary.confidence != "fallback"
            ):
                raise ValueError("classification fallback is inconsistent")
        elif (
            self.fallback_reason is not None
            or self.effective_primary.confidence != "high"
        ):
            raise ValueError("automatic classification is inconsistent")
        if self.detected_primary.confidence == "override":
            raise ValueError("detected classification cannot be an override")
        if (self.detected_primary.confidence == "fallback") != (
            self.fallback_reason is not None
        ):
            raise ValueError("detected classification fallback is inconsistent")

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


def classification_result_from_document(document: JsonObject) -> ClassificationResult:
    """Strictly decode one persisted deterministic classification result."""
    required = {
        "classifier_id",
        "classifier_version",
        "detected_primary",
        "effective_primary",
        "facets",
        "fallback_reason",
        "index_build_id",
        "matched_signals",
        "observations",
        "repository_fingerprint",
        "schema_version",
        "selection_source",
        "taxonomy_version",
        "template_override",
        "topology",
    }
    if set(document) != required:
        raise ValueError("classification document fields are invalid")
    detected = _object(document["detected_primary"])
    effective = _object(document["effective_primary"])
    topology = _object(document["topology"])
    result = ClassificationResult(
        repository_fingerprint=_string(document["repository_fingerprint"]),
        index_build_id=_string(document["index_build_id"]),
        selection_source=_selection_source(document["selection_source"]),
        detected_primary=_scored_primary(detected),
        effective_primary=_scored_primary(effective),
        topology=_scored_taxon(topology),
        facets=tuple(
            _scored_taxon(_object(item)) for item in _array(document["facets"])
        ),
        matched_signals=tuple(
            _matched_signal(_object(item))
            for item in _array(document["matched_signals"])
        ),
        observations=tuple(
            _observation(_object(item)) for item in _array(document["observations"])
        ),
        template_override=_optional_string(document["template_override"]),
        fallback_reason=_fallback_reason(document["fallback_reason"]),
        schema_version=_string(document["schema_version"]),
        classifier_id=_string(document["classifier_id"]),
        classifier_version=_string(document["classifier_version"]),
        taxonomy_version=_string(document["taxonomy_version"]),
    )
    return result


def _scored_primary(document: JsonObject) -> ScoredPrimary:
    if set(document) != {"confidence", "id", "score"}:
        raise ValueError("scored primary fields are invalid")
    confidence = _string(document["confidence"])
    if confidence not in {"high", "fallback", "override"}:
        raise ValueError("classification confidence is invalid")
    return ScoredPrimary(
        _string(document["id"]),
        _integer(document["score"]),
        confidence,  # type: ignore[arg-type]
    )


def _scored_taxon(document: JsonObject) -> ScoredTaxon:
    if set(document) != {"id", "score"}:
        raise ValueError("scored taxon fields are invalid")
    return ScoredTaxon(_string(document["id"]), _integer(document["score"]))


def _matched_signal(document: JsonObject) -> MatchedSignal:
    if set(document) != {"id", "paths", "weight"}:
        raise ValueError("matched signal fields are invalid")
    return MatchedSignal(
        _string(document["id"]),
        _integer(document["weight"]),
        tuple(_string(item) for item in _array(document["paths"])),
    )


def _observation(document: JsonObject) -> ClassificationObservation:
    if set(document) != {"code", "path"}:
        raise ValueError("classification observation fields are invalid")
    code = _string(document["code"])
    if code not in {"manifest_malformed", "manifest_oversized"}:
        raise ValueError("classification observation code is invalid")
    return ClassificationObservation(code, _string(document["path"]))  # type: ignore[arg-type]


def _selection_source(value: JsonValue) -> SelectionSource:
    source = _string(value)
    if source not in {"automatic", "fallback", "override"}:
        raise ValueError("classification selection source is invalid")
    return source  # type: ignore[return-value]


def _fallback_reason(value: JsonValue) -> FallbackReason | None:
    if value is None:
        return None
    reason = _string(value)
    if reason not in {"below_threshold", "tied", "ambiguous"}:
        raise ValueError("classification fallback reason is invalid")
    return reason  # type: ignore[return-value]


def _object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("classification value must be an object")
    return value


def _array(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ValueError("classification value must be an array")
    return value


def _string(value: JsonValue) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("classification value must be a non-empty string")
    return value


def _optional_string(value: JsonValue) -> str | None:
    return None if value is None else _string(value)


def _integer(value: JsonValue) -> int:
    if type(value) is not int:
        raise ValueError("classification value must be an integer")
    return value


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
