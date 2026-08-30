"""Strict immutable Schema 1.0 contracts for the Knowledge Map artifact."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields
from pathlib import PurePosixPath
from typing import Any, ClassVar, Literal, Self, cast

from repo_dive.schema import JsonObject

KNOWLEDGE_MAP_SCHEMA_VERSION = "1.0"
KNOWLEDGE_MAP_ALGORITHM_ID = "builtin-knowledge-map"
KNOWLEDGE_MAP_ALGORITHM_VERSION = "1"

NodeKind = Literal["repository", "module", "file", "symbol"]
Origin = Literal["parser", "derived"]
ScopeKind = Literal["cluster", "flow", "tour"]


def canonical_bytes(value: object) -> bytes:
    """Return canonical JSON bytes without a trailing newline."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return f"{prefix}:{digest.hexdigest()}"


def _positive(values: tuple[int, ...]) -> None:
    if any(type(value) is not int or value <= 0 for value in values):
        raise ValueError("budget fields must be positive integers")


def _strict(document: object, expected: set[str], name: str) -> dict[str, Any]:
    if type(document) is not dict:
        raise ValueError(f"{name} must be an object")
    value = cast(dict[str, Any], document)
    if set(value) != expected:
        raise ValueError(f"{name} fields do not match Schema 1.0")
    return value


def _ordered_unique(values: tuple[str, ...], name: str) -> None:
    if any(type(value) is not str or not value for value in values):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")


def _path(value: str) -> None:
    candidate = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or candidate.is_absolute()
        or str(candidate) != value
        or ".." in candidate.parts
    ):
        raise ValueError("path must be repository-relative POSIX")


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer of at least {minimum}")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _confidence(value: object, name: str) -> float:
    if type(value) not in {int, float}:
        raise ValueError(f"{name} must be finite and between zero and one")
    numeric = cast(float, value)
    if not math.isfinite(numeric) or not 0 <= numeric <= 1:
        raise ValueError(f"{name} must be finite and between zero and one")
    return float(numeric)


@dataclass(frozen=True, slots=True)
class MapSource:
    repository_fingerprint: str
    index_build_id: str
    index_schema_version: int
    source_control: str
    source_commit: str | None
    source_dirty: bool | None

    def __post_init__(self) -> None:
        _text(self.repository_fingerprint, "repository fingerprint")
        _text(self.index_build_id, "index build ID")
        _integer(self.index_schema_version, "index schema version", minimum=1)
        if self.source_control not in {"git", "non_git"}:
            raise ValueError("source control is invalid")
        if self.source_control == "non_git" and (
            self.source_commit is not None or self.source_dirty is not None
        ):
            raise ValueError("non-Git source cannot contain Git identity")
        if self.source_control == "git" and self.source_dirty is None:
            raise ValueError("Git source requires dirty state")
        if self.source_dirty is not None:
            _boolean(self.source_dirty, "source dirty state")
        if self.source_commit is not None and (
            len(self.source_commit) != 40
            or any(
                character not in "0123456789abcdef" for character in self.source_commit
            )
        ):
            raise ValueError("source commit must be a full lowercase Git object ID")

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "source")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class DerivationParameters:
    schema_version: str
    source_fact_budget: int
    node_budget: int
    edge_budget: int
    contributing_relationship_ids_per_edge: int
    resolution_candidates_per_reference: int
    cluster_budget: int
    minimum_cluster_files: int
    flow_budget: int
    flow_depth: int
    nodes_per_flow: int
    edges_per_flow: int
    tour_budget: int

    def __post_init__(self) -> None:
        if self.schema_version != KNOWLEDGE_MAP_SCHEMA_VERSION:
            raise ValueError("budget schema version is unsupported")
        _positive(
            tuple(cast(int, getattr(self, item.name)) for item in fields(self)[1:])
        )

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        return cls(**_strict(document, _field_names(cls), "derivation parameters"))


@dataclass(frozen=True, slots=True)
class CapacityLimits:
    artifact_byte_budget: int
    evidence_snapshots: int
    evidence_references_per_snapshot: int
    enrichment_records: int
    records_per_scope: int
    claims_per_record: int
    fact_node_ids_per_claim: int
    related_node_ids_per_claim: int
    evidence_ids_per_claim: int
    enrichment_input_bytes: int

    def __post_init__(self) -> None:
        _positive(tuple(cast(int, getattr(self, item.name)) for item in fields(self)))

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        return cls(**_strict(document, _field_names(cls), "capacity limits"))


@dataclass(frozen=True, slots=True)
class MapBuildBudgets:
    source_fact_budget: int
    artifact_byte_budget: int
    node_budget: int
    edge_budget: int
    contributing_relationship_ids_per_edge: int
    resolution_candidates_per_reference: int
    cluster_budget: int
    minimum_cluster_files: int
    flow_budget: int
    flow_depth: int
    nodes_per_flow: int
    edges_per_flow: int
    tour_budget: int
    evidence_snapshots: int
    evidence_references_per_snapshot: int
    enrichment_records: int
    records_per_scope: int
    claims_per_record: int
    fact_node_ids_per_claim: int
    related_node_ids_per_claim: int
    evidence_ids_per_claim: int
    enrichment_input_bytes: int
    schema_version: str = KNOWLEDGE_MAP_SCHEMA_VERSION

    FILE_FIELDS: ClassVar[tuple[str, ...]] = (
        "schema_version",
        "node_budget",
        "edge_budget",
        "contributing_relationship_ids_per_edge",
        "resolution_candidates_per_reference",
        "cluster_budget",
        "minimum_cluster_files",
        "flow_budget",
        "flow_depth",
        "nodes_per_flow",
        "edges_per_flow",
        "tour_budget",
        "evidence_snapshots",
        "evidence_references_per_snapshot",
        "enrichment_records",
        "records_per_scope",
        "claims_per_record",
        "fact_node_ids_per_claim",
        "related_node_ids_per_claim",
        "evidence_ids_per_claim",
        "enrichment_input_bytes",
    )

    def __post_init__(self) -> None:
        if self.schema_version != KNOWLEDGE_MAP_SCHEMA_VERSION:
            raise ValueError("budget schema version is unsupported")
        _positive(
            tuple(
                cast(int, getattr(self, item.name))
                for item in fields(self)
                if item.name != "schema_version"
            )
        )
        if self.edges_per_flow > self.nodes_per_flow:
            raise ValueError("edges_per_flow cannot exceed nodes_per_flow")

    @classmethod
    def from_budget_document(
        cls,
        document: object,
        *,
        source_fact_budget: int,
        artifact_byte_budget: int,
    ) -> Self:
        value = _strict(document, set(cls.FILE_FIELDS), "budget document")
        return cls(
            source_fact_budget=source_fact_budget,
            artifact_byte_budget=artifact_byte_budget,
            **value,
        )

    def derivation_parameters(self) -> DerivationParameters:
        names = _field_names(DerivationParameters)
        return DerivationParameters(**{name: getattr(self, name) for name in names})

    def capacity_limits(self) -> CapacityLimits:
        names = _field_names(CapacityLimits)
        return CapacityLimits(**{name: getattr(self, name) for name in names})


@dataclass(frozen=True, slots=True)
class LanguageCoverage:
    language: str
    file_count: int
    indexed_file_count: int
    symbol_count: int
    relationship_count: int
    relationship_kinds: tuple[tuple[str, int], ...]
    graph_capability: str

    def __post_init__(self) -> None:
        _text(self.language, "coverage language")
        for name in (
            "file_count",
            "indexed_file_count",
            "symbol_count",
            "relationship_count",
        ):
            _integer(cast(int, getattr(self, name)), name)
        if self.indexed_file_count > self.file_count:
            raise ValueError("language indexed-file coverage is inconsistent")
        if self.graph_capability not in {"full", "containment_only", "none"}:
            raise ValueError("language graph capability is invalid")
        if self.relationship_kinds != tuple(sorted(self.relationship_kinds)):
            raise ValueError("language relationship coverage must be sorted")
        if (
            len({kind for kind, _ in self.relationship_kinds})
            != len(self.relationship_kinds)
            or any(
                type(kind) is not str or not kind or type(count) is not int or count < 0
                for kind, count in self.relationship_kinds
            )
            or self.relationship_count
            != sum(count for _, count in self.relationship_kinds)
        ):
            raise ValueError("language relationship coverage is inconsistent")

    def to_document(self) -> JsonObject:
        value = _dataclass_document(self)
        value["relationship_kinds"] = [list(item) for item in self.relationship_kinds]
        return value

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "language coverage")
        value["relationship_kinds"] = _pairs(
            value["relationship_kinds"], "language relationship kinds"
        )
        return cls(**value)


@dataclass(frozen=True, slots=True)
class MapCoverage:
    total_files: int = 0
    indexed_files: int = 0
    skipped_files: int = 0
    symbols: int = 0
    relationship_occurrences: int = 0
    unresolved_references: int = 0
    ambiguous_references: int = 0
    included_nodes: int = 0
    omitted_nodes: int = 0
    included_edges: int = 0
    omitted_edges: int = 0
    included_clusters: int = 0
    omitted_clusters: int = 0
    included_flows: int = 0
    omitted_flows: int = 0
    included_tour_items: int = 0
    omitted_tour_items: int = 0
    languages: tuple[tuple[str, int], ...] = ()
    relationship_kinds: tuple[tuple[str, int], ...] = ()
    parser_coverage: tuple[LanguageCoverage, ...] = ()
    observations: tuple[str, ...] = ()
    omission_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        counts = (
            self.total_files,
            self.indexed_files,
            self.skipped_files,
            self.symbols,
            self.relationship_occurrences,
            self.unresolved_references,
            self.ambiguous_references,
            self.included_nodes,
            self.omitted_nodes,
            self.included_edges,
            self.omitted_edges,
            self.included_clusters,
            self.omitted_clusters,
            self.included_flows,
            self.omitted_flows,
            self.included_tour_items,
            self.omitted_tour_items,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("coverage counts must be non-negative integers")
        if self.indexed_files + self.skipped_files != self.total_files:
            raise ValueError("coverage file counts are inconsistent")
        for values in (self.languages, self.relationship_kinds):
            if (
                values != tuple(sorted(values))
                or len({name for name, _ in values}) != len(values)
                or any(
                    type(name) is not str
                    or not name
                    or type(count) is not int
                    or count < 0
                    for name, count in values
                )
            ):
                raise ValueError("coverage breakdowns must be sorted and non-negative")
        _ordered_unique(self.observations, "observations")
        _ordered_unique(self.omission_reasons, "omission reasons")
        if self.observations != tuple(sorted(self.observations)) or (
            self.omission_reasons != tuple(sorted(self.omission_reasons))
        ):
            raise ValueError("coverage audit values must be sorted")
        if self.parser_coverage != tuple(
            sorted(self.parser_coverage, key=lambda item: item.language)
        ) or len({item.language for item in self.parser_coverage}) != len(
            self.parser_coverage
        ):
            raise ValueError("parser coverage must be sorted and unique")
        if tuple((item.language, item.file_count) for item in self.parser_coverage) != (
            self.languages
        ):
            raise ValueError("parser coverage does not match language totals")
        if (
            sum(item.indexed_file_count for item in self.parser_coverage)
            != (self.indexed_files)
            or sum(item.symbol_count for item in self.parser_coverage) != self.symbols
        ):
            raise ValueError("parser coverage counts are inconsistent")
        if sum(item.relationship_count for item in self.parser_coverage) != (
            self.relationship_occurrences
        ):
            raise ValueError("parser relationship coverage is inconsistent")

    def to_document(self) -> JsonObject:
        value = _dataclass_document(self)
        value["languages"] = [list(item) for item in self.languages]
        value["relationship_kinds"] = [list(item) for item in self.relationship_kinds]
        value["parser_coverage"] = [item.to_document() for item in self.parser_coverage]
        return value

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "coverage")
        value["languages"] = _pairs(value["languages"], "languages")
        value["relationship_kinds"] = _pairs(
            value["relationship_kinds"], "relationship kinds"
        )
        if type(value["parser_coverage"]) is not list:
            raise ValueError("parser coverage must be an array")
        value["parser_coverage"] = tuple(
            LanguageCoverage.from_document(item) for item in value["parser_coverage"]
        )
        value["observations"] = _strings(value["observations"], "observations")
        value["omission_reasons"] = _strings(
            value["omission_reasons"], "omission reasons"
        )
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ImportanceSignals:
    """Named raw inputs used by the deterministic importance rank."""

    unique_fan_in: int
    unique_fan_out: int
    cross_module_bridge: bool
    entrypoint: bool
    public_api: bool
    documentation_mentions: int
    distinct_test_files: int

    def __post_init__(self) -> None:
        for name in (
            "unique_fan_in",
            "unique_fan_out",
            "documentation_mentions",
            "distinct_test_files",
        ):
            _integer(cast(int, getattr(self, name)), name)
        for name in ("cross_module_bridge", "entrypoint", "public_api"):
            _boolean(cast(bool, getattr(self, name)), name)

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        return cls(**_strict(document, _field_names(cls), "importance signals"))


@dataclass(frozen=True, slots=True)
class ImportanceRank:
    """Named lexicographic components; lower tuples rank first."""

    entrypoint: int
    unique_fan_in: int
    cross_module_bridge: int
    unique_fan_out: int
    public_api: int
    path: str
    node_id: str

    def __post_init__(self) -> None:
        if any(
            type(getattr(self, name)) is not int
            for name in (
                "entrypoint",
                "unique_fan_in",
                "cross_module_bridge",
                "unique_fan_out",
                "public_api",
            )
        ):
            raise ValueError("importance rank numeric components must be integers")
        _text(self.node_id, "importance rank node ID")

    def as_tuple(self) -> tuple[int | str, ...]:
        return (
            self.entrypoint,
            self.unique_fan_in,
            self.cross_module_bridge,
            self.unique_fan_out,
            self.public_api,
            self.path,
            self.node_id,
        )

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        return cls(**_strict(document, _field_names(cls), "importance rank"))


@dataclass(frozen=True, slots=True)
class FactNode:
    id: str
    kind: NodeKind
    origin: Origin
    name: str
    path: str | None
    start_line: int | None
    end_line: int | None
    language: str | None
    parent_id: str | None
    parser_symbol_id: str | None
    importance_signals: ImportanceSignals | None = None
    importance_rank: ImportanceRank | None = None
    resolution_status: str | None = None
    resolution_candidate_ids: tuple[str, ...] = ()
    resolution_rule_id: str | None = None
    resolution_candidates_truncated: bool = False

    def __post_init__(self) -> None:
        if not self.id or self.kind not in {"repository", "module", "file", "symbol"}:
            raise ValueError("fact node identity or kind is invalid")
        if self.origin not in {"parser", "derived"} or not self.name:
            raise ValueError("fact node origin or name is invalid")
        if self.path is not None:
            _path(self.path)
        if (self.start_line is None) != (self.end_line is None):
            raise ValueError("fact node line range must be complete")
        if self.start_line is not None and (
            self.start_line < 1 or cast(int, self.end_line) < self.start_line
        ):
            raise ValueError("fact node line range is invalid")
        if self.kind == "repository" and self.parent_id is not None:
            raise ValueError("repository node cannot have a parent")
        if self.kind == "repository" and any(
            value is not None
            for value in (
                self.path,
                self.start_line,
                self.end_line,
                self.language,
                self.parser_symbol_id,
            )
        ):
            raise ValueError("repository node cannot contain source location fields")
        if self.kind == "module" and self.path is not None:
            raise ValueError("module node cannot contain a source path")
        if self.kind == "file" and (
            self.path is None
            or self.parent_id is None
            or self.start_line is not None
            or self.parser_symbol_id is not None
        ):
            raise ValueError("file node source and ownership fields are invalid")
        if self.kind == "symbol" and (
            self.path is None
            or self.parent_id is None
            or self.start_line is None
            or not self.parser_symbol_id
            or self.origin != "parser"
        ):
            raise ValueError("symbol node source and parser identity are invalid")
        if (self.importance_signals is None) != (self.importance_rank is None):
            raise ValueError("importance signals and rank must be present together")
        if self.resolution_status not in {
            None,
            "resolved",
            "ambiguous",
            "unresolved",
            "unsupported",
        }:
            raise ValueError("resolution status is invalid")
        _ordered_unique(self.resolution_candidate_ids, "resolution candidates")
        _boolean(
            self.resolution_candidates_truncated,
            "resolution candidate truncation",
        )
        if self.resolution_status in {"resolved", "ambiguous"}:
            if not self.resolution_candidate_ids or self.resolution_rule_id is None:
                raise ValueError("resolved and ambiguous references require candidates")
            if (
                self.resolution_status == "resolved"
                and len(self.resolution_candidate_ids) != 1
            ):
                raise ValueError("resolved reference requires exactly one candidate")
        elif (
            self.resolution_candidate_ids
            or self.resolution_rule_id is not None
            or self.resolution_candidates_truncated
        ):
            raise ValueError(
                "non-candidate resolution state contains candidate metadata"
            )
        if self.kind != "symbol" and self.resolution_status is not None:
            raise ValueError("only symbols can contain resolution state")

    def to_document(self) -> JsonObject:
        value = _dataclass_document(self)
        value["importance_signals"] = (
            self.importance_signals.to_document()
            if self.importance_signals is not None
            else None
        )
        value["importance_rank"] = (
            self.importance_rank.to_document()
            if self.importance_rank is not None
            else None
        )
        return value

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "fact node")
        value["importance_signals"] = (
            ImportanceSignals.from_document(value["importance_signals"])
            if value["importance_signals"] is not None
            else None
        )
        value["importance_rank"] = (
            ImportanceRank.from_document(value["importance_rank"])
            if value["importance_rank"] is not None
            else None
        )
        value["resolution_candidate_ids"] = _strings(
            value["resolution_candidate_ids"], "resolution candidates"
        )
        return cls(**value)


@dataclass(frozen=True, slots=True)
class FactEdge:
    id: str
    source_id: str
    target_id: str
    kind: str
    origin: Origin
    relationship_id: str | None
    rule_id: str | None
    occurrence_count: int
    unique_source_count: int
    unique_target_count: int
    confidence_min: float
    confidence_max: float
    contributor_total: int
    contributing_relationship_ids: tuple[str, ...]
    contributors_truncated: bool
    evidence_path: str | None = None
    evidence_start_line: int | None = None
    evidence_end_line: int | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.source_id or not self.target_id or not self.kind:
            raise ValueError("fact edge identity is invalid")
        if self.origin not in {"parser", "derived"}:
            raise ValueError("fact edge origin is invalid")
        if not (
            math.isfinite(self.confidence_min)
            and math.isfinite(self.confidence_max)
            and 0 <= self.confidence_min <= self.confidence_max <= 1
        ):
            raise ValueError("fact edge confidence is invalid")
        counts = (
            self.occurrence_count,
            self.unique_source_count,
            self.unique_target_count,
            self.contributor_total,
        )
        if any(type(value) is not int or value < 1 for value in counts):
            raise ValueError("fact edge counts must be positive")
        _boolean(self.contributors_truncated, "fact edge contributor truncation")
        _ordered_unique(self.contributing_relationship_ids, "contributors")
        if self.contributing_relationship_ids != tuple(
            sorted(self.contributing_relationship_ids)
        ):
            raise ValueError("fact edge contributors must be sorted")
        if len(self.contributing_relationship_ids) > self.contributor_total:
            raise ValueError("fact edge contributor counts are inconsistent")
        if self.contributors_truncated != (
            len(self.contributing_relationship_ids) < self.contributor_total
        ):
            raise ValueError("fact edge truncation flag is inconsistent")
        if self.origin == "parser" and not self.relationship_id:
            raise ValueError("parser edge requires relationship ID")
        if self.origin == "parser" and self.rule_id is not None:
            raise ValueError("parser edge cannot contain a derivation rule")
        if self.origin == "derived" and not self.rule_id:
            raise ValueError("derived edge requires rule ID")
        if self.origin == "derived" and self.relationship_id is not None:
            raise ValueError("derived edge cannot contain one parser relationship ID")
        evidence = (
            self.evidence_path,
            self.evidence_start_line,
            self.evidence_end_line,
        )
        if any(value is not None for value in evidence) and not all(
            value is not None for value in evidence
        ):
            raise ValueError("fact edge Evidence location must be complete")
        if self.origin == "parser" and self.evidence_path is None:
            raise ValueError("parser edge requires exact Evidence")
        if self.origin == "derived" and self.evidence_path is not None:
            raise ValueError("derived edge cannot claim one exact Evidence location")
        if self.evidence_path is not None:
            _path(self.evidence_path)
            if (
                type(self.evidence_start_line) is not int
                or type(self.evidence_end_line) is not int
                or self.evidence_start_line < 1
                or self.evidence_end_line < self.evidence_start_line
            ):
                raise ValueError("fact edge Evidence range is invalid")

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "fact edge")
        value["contributing_relationship_ids"] = _strings(
            value["contributing_relationship_ids"], "contributors"
        )
        return cls(**value)


@dataclass(frozen=True, slots=True)
class CycleGroup:
    id: str
    member_module_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    rule_id: str = "tarjan_scc_v1"

    def __post_init__(self) -> None:
        _text(self.id, "cycle group ID")
        _text(self.rule_id, "cycle group rule")
        _ordered_unique(self.member_module_ids, "cycle group members")
        _ordered_unique(self.edge_ids, "cycle group edges")
        if not self.member_module_ids:
            raise ValueError("cycle group requires at least one module")

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "cycle group")
        value["member_module_ids"] = _strings(
            value["member_module_ids"], "cycle group members"
        )
        value["edge_ids"] = _strings(value["edge_ids"], "cycle group edges")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class Cluster:
    id: str
    member_node_ids: tuple[str, ...]
    formation_signals: tuple[str, ...]
    internal_unique_edges: int
    external_unique_edges: int
    internal_occurrences: int
    external_occurrences: int
    scc_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.member_node_ids:
            raise ValueError("cluster identity and members must not be empty")
        for name in ("member_node_ids", "formation_signals", "scc_ids"):
            _ordered_unique(cast(tuple[str, ...], getattr(self, name)), name)
        if (
            min(
                self.internal_unique_edges,
                self.external_unique_edges,
                self.internal_occurrences,
                self.external_occurrences,
            )
            < 0
        ):
            raise ValueError("cluster counts must be non-negative")

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "cluster")
        for name in ("member_node_ids", "formation_signals", "scc_ids"):
            value[name] = _strings(value[name], name)
        return cls(**value)


@dataclass(frozen=True, slots=True)
class Layer:
    id: str
    kind: str
    rule_ids: tuple[str, ...]
    matched_signals: tuple[str, ...]
    confidence: float
    member_node_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id or self.kind not in {
            "Interface/CLI",
            "Application",
            "Domain",
            "Infrastructure",
            "Persistence",
            "Tests",
            "unclassified",
        }:
            raise ValueError("layer identity or kind is invalid")
        _confidence(self.confidence, "layer confidence")
        for name in ("rule_ids", "matched_signals", "member_node_ids"):
            _ordered_unique(cast(tuple[str, ...], getattr(self, name)), name)
        if not self.rule_ids or not self.member_node_ids:
            raise ValueError("layer requires rules and members")

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "layer")
        for name in ("rule_ids", "matched_signals", "member_node_ids"):
            value[name] = _strings(value[name], name)
        return cls(**value)


@dataclass(frozen=True, slots=True)
class StaticFlow:
    id: str
    root_node_id: str
    step_node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    transition_kinds: tuple[str, ...]
    terminal_reason: str
    confidence: float
    incomplete_coverage: bool
    truncated: bool
    root_kind: str = "named_entrypoint"
    transition_semantics: tuple[str, ...] = ()
    representative_relationship_ids: tuple[str, ...] = ()
    execution_semantics: str = "static"
    import_fallback: bool = False
    suppressed_utility_node_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.id
            or not self.step_node_ids
            or self.step_node_ids[0] != self.root_node_id
        ):
            raise ValueError("flow identity, root, or steps are invalid")
        if len(self.edge_ids) != max(0, len(self.step_node_ids) - 1):
            raise ValueError("flow edge and step counts are inconsistent")
        if len(self.transition_kinds) != len(self.edge_ids):
            raise ValueError("flow transition and edge counts are inconsistent")
        if any(kind not in {"calls", "imports"} for kind in self.transition_kinds):
            raise ValueError("flow transition kind is invalid")
        if len(self.transition_semantics) != len(self.edge_ids):
            raise ValueError(
                "flow transition semantics and edge counts are inconsistent"
            )
        if len(self.representative_relationship_ids) != len(self.edge_ids):
            raise ValueError("flow occurrence trace and edge counts are inconsistent")
        _ordered_unique(self.step_node_ids, "flow steps")
        _ordered_unique(self.edge_ids, "flow edges")
        if self.terminal_reason not in {
            "terminal",
            "cycle",
            "depth_limit",
            "size_limit",
            "candidate_budget",
            "utility_suppressed",
        }:
            raise ValueError("flow terminal reason is invalid")
        _confidence(self.confidence, "flow confidence")
        _boolean(self.incomplete_coverage, "flow incomplete coverage")
        _boolean(self.truncated, "flow truncation")
        _boolean(self.import_fallback, "flow import fallback")
        if self.root_kind not in {"named_entrypoint", "main_module", "project_script"}:
            raise ValueError("flow root kind is invalid")
        if self.execution_semantics != "static":
            raise ValueError("flow execution semantics must be static")
        if any(
            value not in {"runtime_call", "structural_import_fallback"}
            for value in self.transition_semantics
        ):
            raise ValueError("flow transition semantics are invalid")
        expected_semantics = tuple(
            "runtime_call" if kind == "calls" else "structural_import_fallback"
            for kind in self.transition_kinds
        )
        if self.transition_semantics != expected_semantics:
            raise ValueError("flow transition semantics do not match edge kinds")
        if self.import_fallback != ("imports" in self.transition_kinds):
            raise ValueError("flow import-fallback flag is inconsistent")
        if self.terminal_reason == "utility_suppressed" and not (
            self.suppressed_utility_node_ids
        ):
            raise ValueError("utility-suppressed flow requires suppressed node IDs")
        if self.terminal_reason != "utility_suppressed" and (
            self.suppressed_utility_node_ids
        ):
            raise ValueError("non-utility flow cannot contain suppressed utility nodes")
        _ordered_unique(
            self.representative_relationship_ids,
            "flow representative relationship IDs",
        )
        _ordered_unique(
            self.suppressed_utility_node_ids,
            "flow suppressed utility nodes",
        )

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "flow")
        for name in (
            "step_node_ids",
            "edge_ids",
            "transition_kinds",
            "transition_semantics",
            "representative_relationship_ids",
            "suppressed_utility_node_ids",
        ):
            value[name] = _strings(value[name], name)
        return cls(**value)


@dataclass(frozen=True, slots=True)
class TourItem:
    id: str
    target_kind: str
    target_id: str
    fact_node_id: str | None
    rank: tuple[int | str, ...]
    next_item_id: str | None

    def __post_init__(self) -> None:
        _text(self.id, "tour item ID")
        if self.target_kind not in {"node", "cluster", "flow"}:
            raise ValueError("tour target kind is invalid")
        _text(self.target_id, "tour target ID")
        if (self.target_kind == "node") != (self.fact_node_id is not None):
            raise ValueError("tour fact-node projection is inconsistent")
        if any(type(value) not in {int, str} for value in self.rank):
            raise ValueError("tour rank values are invalid")

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "tour item")
        if type(value["rank"]) is not list:
            raise ValueError("tour rank must be an array")
        value["rank"] = tuple(value["rank"])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ScopeContract:
    scope_id: str
    scope_kind: ScopeKind
    contract_hash: str
    allowed_fact_node_ids: tuple[str, ...]
    required_anchor_fact_node_ids: tuple[str, ...]
    allowed_record_kinds: tuple[str, ...]
    allowed_claim_kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.scope_id, "scope ID")
        if self.scope_kind not in {"cluster", "flow", "tour"}:
            raise ValueError("scope kind is invalid")
        for name in (
            "allowed_fact_node_ids",
            "required_anchor_fact_node_ids",
            "allowed_record_kinds",
            "allowed_claim_kinds",
        ):
            _ordered_unique(cast(tuple[str, ...], getattr(self, name)), name)
        if not self.allowed_fact_node_ids or not self.required_anchor_fact_node_ids:
            raise ValueError("scope contract requires allowed nodes and anchors")
        if not self.allowed_record_kinds or not self.allowed_claim_kinds:
            raise ValueError("scope contract requires record and claim permissions")
        if not set(self.allowed_record_kinds) <= {
            "cluster_label",
            "flow_explanation",
            "concept",
            "reading_guidance",
        } or not set(self.allowed_claim_kinds) <= {
            "label",
            "summary",
            "responsibility",
            "flow_explanation",
            "concept_description",
            "reading_guidance",
            "association",
        }:
            raise ValueError("scope contract permissions are invalid")
        expected = canonical_sha256(self._hash_document())
        if self.contract_hash != expected:
            raise ValueError("scope contract hash does not match content")

    @classmethod
    def create(
        cls,
        *,
        scope_id: str,
        scope_kind: ScopeKind,
        allowed_fact_node_ids: tuple[str, ...],
        required_anchor_fact_node_ids: tuple[str, ...],
        allowed_record_kinds: tuple[str, ...],
        allowed_claim_kinds: tuple[str, ...],
    ) -> Self:
        values: dict[str, Any] = {
            "scope_id": scope_id,
            "scope_kind": scope_kind,
            "allowed_fact_node_ids": allowed_fact_node_ids,
            "required_anchor_fact_node_ids": required_anchor_fact_node_ids,
            "allowed_record_kinds": allowed_record_kinds,
            "allowed_claim_kinds": allowed_claim_kinds,
        }
        return cls(contract_hash=canonical_sha256(values), **values)

    def _hash_document(self) -> JsonObject:
        value = self.to_document()
        del value["contract_hash"]
        return value

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "scope contract")
        for name in (
            "allowed_fact_node_ids",
            "required_anchor_fact_node_ids",
            "allowed_record_kinds",
            "allowed_claim_kinds",
        ):
            value[name] = _strings(value[name], name)
        return cls(**value)


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    chunk_id: str
    content_hash: str
    path: str
    start_line: int
    end_line: int
    symbol_id: str | None
    role: str
    anchor_fact_node_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for value, name in (
            (self.evidence_id, "Evidence ID"),
            (self.chunk_id, "Chunk ID"),
            (self.content_hash, "Evidence content hash"),
            (self.role, "Evidence role"),
        ):
            _text(value, name)
        _path(self.path)
        if (
            type(self.start_line) is not int
            or type(self.end_line) is not int
            or self.start_line < 1
            or self.end_line < self.start_line
        ):
            raise ValueError("Evidence line range is invalid")
        if self.role not in {"direct", "supplemental", "definition", "context"}:
            raise ValueError("Evidence role is invalid")
        _ordered_unique(self.anchor_fact_node_ids, "Evidence anchors")
        if not self.anchor_fact_node_ids:
            raise ValueError("Evidence requires at least one fact-node anchor")

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "Evidence reference")
        value["anchor_fact_node_ids"] = _strings(
            value["anchor_fact_node_ids"], "Evidence anchors"
        )
        return cls(**value)


@dataclass(frozen=True, slots=True)
class RetrievalParameters:
    """Immutable, strictly decoded Evidence retrieval parameters."""

    max_results: int
    strategy: str
    rrf_k: int
    channel_weights: tuple[tuple[str, float], ...]
    overlap_threshold: float

    def __post_init__(self) -> None:
        _integer(self.max_results, "retrieval max results", minimum=1)
        _integer(self.rrf_k, "retrieval RRF k")
        _text(self.strategy, "retrieval strategy")
        names = tuple(name for name, _ in self.channel_weights)
        _ordered_unique(names, "retrieval channel names")
        if (
            not names
            or any(
                type(weight) not in {int, float}
                or not math.isfinite(weight)
                or weight < 0
                for _, weight in self.channel_weights
            )
            or not any(weight > 0 for _, weight in self.channel_weights)
        ):
            raise ValueError("retrieval channel weights are invalid")
        if (
            type(self.overlap_threshold) not in {int, float}
            or not math.isfinite(self.overlap_threshold)
            or not 0 < self.overlap_threshold <= 1
        ):
            raise ValueError("retrieval overlap threshold is invalid")

    def to_document(self) -> JsonObject:
        return {
            "channel_weights": [list(item) for item in self.channel_weights],
            "max_results": self.max_results,
            "overlap_threshold": self.overlap_threshold,
            "rrf_k": self.rrf_k,
            "strategy": self.strategy,
        }

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "retrieval parameters")
        weights = value["channel_weights"]
        if type(weights) is not list:
            raise ValueError("retrieval channel weights must be an ordered array")
        parsed: list[tuple[str, float]] = []
        for item in weights:
            if (
                type(item) is not list
                or len(item) != 2
                or type(item[0]) is not str
                or type(item[1]) not in {int, float}
            ):
                raise ValueError("retrieval channel weight entry is invalid")
            parsed.append((item[0], float(item[1])))
        value["channel_weights"] = tuple(parsed)
        return cls(**value)


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    schema_version: str
    scope_id: str
    scope_kind: ScopeKind
    scope_contract_hash: str
    deterministic_revision: str
    repository_fingerprint: str
    index_build_id: str
    index_schema_version: int
    source_control: str
    source_commit: str | None
    source_dirty: bool | None
    query: str
    query_plan_hash: str
    retrieval_parameters: RetrievalParameters
    token_budget: int
    estimated_tokens: int
    reserved_tokens: int
    token_estimator: str
    truncated: bool
    reference_count: int
    references: tuple[EvidenceRef, ...]
    snapshot_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != KNOWLEDGE_MAP_SCHEMA_VERSION:
            raise ValueError("Evidence snapshot schema version is unsupported")
        if self.reference_count != len(self.references):
            raise ValueError("Evidence reference count is inconsistent")
        if (
            type(self.token_budget) is not int
            or type(self.estimated_tokens) is not int
            or type(self.reserved_tokens) is not int
            or self.token_budget <= 0
            or not 0
            <= self.reserved_tokens
            <= self.estimated_tokens
            <= self.token_budget
        ):
            raise ValueError("Evidence token values are invalid")
        for value, name in (
            (self.scope_id, "Evidence scope ID"),
            (self.scope_contract_hash, "Evidence scope contract hash"),
            (self.deterministic_revision, "Evidence deterministic revision"),
            (self.repository_fingerprint, "Evidence repository fingerprint"),
            (self.index_build_id, "Evidence index build ID"),
            (self.query, "Evidence query"),
            (self.query_plan_hash, "Evidence query plan hash"),
            (self.token_estimator, "Evidence token estimator"),
        ):
            _text(value, name)
        MapSource(
            self.repository_fingerprint,
            self.index_build_id,
            self.index_schema_version,
            self.source_control,
            self.source_commit,
            self.source_dirty,
        )
        _boolean(self.truncated, "Evidence truncation")
        if type(self.reference_count) is not int or self.reference_count < 0:
            raise ValueError("Evidence reference count is invalid")
        evidence_ids = tuple(item.evidence_id for item in self.references)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence IDs must be unique")
        document = self.to_document()
        del document["snapshot_hash"]
        if self.snapshot_hash != canonical_sha256(document):
            raise ValueError("Evidence snapshot hash does not match content")

    def to_document(self) -> JsonObject:
        value = _dataclass_document(self)
        value["retrieval_parameters"] = self.retrieval_parameters.to_document()
        value["references"] = [item.to_document() for item in self.references]
        return value

    @classmethod
    def create(cls, **values: Any) -> Self:
        """Create a snapshot while deriving its reproducible content hash."""
        return cls(snapshot_hash=canonical_sha256(_json_value(values)), **values)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "Evidence snapshot")
        value["retrieval_parameters"] = RetrievalParameters.from_document(
            value["retrieval_parameters"]
        )
        value["references"] = tuple(
            EvidenceRef.from_document(item) for item in value["references"]
        )
        return cls(**value)


@dataclass(frozen=True, slots=True)
class SemanticClaim:
    kind: str
    text: str
    fact_node_ids: tuple[str, ...]
    related_node_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in {
            "label",
            "summary",
            "responsibility",
            "flow_explanation",
            "concept_description",
            "reading_guidance",
            "association",
        }:
            raise ValueError("semantic claim kind is invalid")
        _text(self.text, "semantic claim text")
        if not self.fact_node_ids or not self.evidence_ids:
            raise ValueError("semantic claim requires text, fact nodes, and Evidence")
        for name in ("fact_node_ids", "related_node_ids", "evidence_ids"):
            _ordered_unique(cast(tuple[str, ...], getattr(self, name)), name)

    def to_document(self) -> JsonObject:
        return _dataclass_document(self)

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "semantic claim")
        for name in ("fact_node_ids", "related_node_ids", "evidence_ids"):
            value[name] = _strings(value[name], name)
        return cls(**value)


@dataclass(frozen=True, slots=True)
class EnrichmentRecord:
    id: str
    kind: str
    claims: tuple[SemanticClaim, ...]

    def __post_init__(self) -> None:
        if not self.id or self.kind not in {
            "cluster_label",
            "flow_explanation",
            "concept",
            "reading_guidance",
        }:
            raise ValueError("enrichment record identity or kind is invalid")
        if not self.claims:
            raise ValueError("enrichment record requires claims")
        claim_keys = tuple(
            (claim.kind, claim.text, claim.fact_node_ids, claim.evidence_ids)
            for claim in self.claims
        )
        if len(claim_keys) != len(set(claim_keys)):
            raise ValueError("enrichment record contains duplicate claims")

    def to_document(self) -> JsonObject:
        return {
            "id": self.id,
            "kind": self.kind,
            "claims": [claim.to_document() for claim in self.claims],
        }

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "enrichment record")
        value["claims"] = tuple(
            SemanticClaim.from_document(item) for item in value["claims"]
        )
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ScopeEnrichment:
    schema_version: str
    scope_id: str
    scope_kind: ScopeKind
    scope_contract_hash: str
    evidence_snapshot_hash: str
    canonical_input_bytes: int
    canonical_input_sha256: str
    records: tuple[EnrichmentRecord, ...]
    scope_content_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != KNOWLEDGE_MAP_SCHEMA_VERSION:
            raise ValueError("enrichment schema version is unsupported")
        canonical_input = {
            "schema_version": self.schema_version,
            "scope_id": self.scope_id,
            "records": [record.to_document() for record in self.records],
        }
        encoded = canonical_bytes(canonical_input)
        if self.canonical_input_bytes != len(encoded):
            raise ValueError("canonical enrichment input byte count is inconsistent")
        expected_input_hash = "sha256:" + hashlib.sha256(encoded).hexdigest()
        if self.canonical_input_sha256 != expected_input_hash:
            raise ValueError("canonical enrichment input hash is inconsistent")
        expected_scope_hash = canonical_sha256(
            {
                "scope_contract_hash": self.scope_contract_hash,
                "scope_id": self.scope_id,
                "scope_kind": self.scope_kind,
                "evidence_snapshot_hash": self.evidence_snapshot_hash,
                "records": [record.to_document() for record in self.records],
            }
        )
        if self.scope_content_hash != expected_scope_hash:
            raise ValueError("enrichment scope content hash is inconsistent")
        record_ids = tuple(record.id for record in self.records)
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("enrichment record IDs must be unique within a scope")

    def to_document(self) -> JsonObject:
        value = _dataclass_document(self)
        value["records"] = [item.to_document() for item in self.records]
        return value

    @classmethod
    def create(
        cls,
        *,
        schema_version: str,
        scope_id: str,
        scope_kind: ScopeKind,
        scope_contract_hash: str,
        evidence_snapshot_hash: str,
        records: tuple[EnrichmentRecord, ...],
    ) -> Self:
        """Create canonical input and scope hashes without lifecycle fields."""
        canonical_input = {
            "schema_version": schema_version,
            "scope_id": scope_id,
            "records": [record.to_document() for record in records],
        }
        encoded = canonical_bytes(canonical_input)
        input_hash = "sha256:" + hashlib.sha256(encoded).hexdigest()
        scope_hash = canonical_sha256(
            {
                "scope_contract_hash": scope_contract_hash,
                "scope_id": scope_id,
                "scope_kind": scope_kind,
                "evidence_snapshot_hash": evidence_snapshot_hash,
                "records": [record.to_document() for record in records],
            }
        )
        return cls(
            schema_version,
            scope_id,
            scope_kind,
            scope_contract_hash,
            evidence_snapshot_hash,
            len(encoded),
            input_hash,
            records,
            scope_hash,
        )

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "scope enrichment")
        value["records"] = tuple(
            EnrichmentRecord.from_document(item) for item in value["records"]
        )
        return cls(**value)


@dataclass(frozen=True, slots=True)
class KnowledgeMapArtifact:
    schema_version: str
    algorithm_id: str
    algorithm_version: str
    artifact_revision: int
    content_hash: str
    deterministic_revision: str
    semantic_revision: str
    source: MapSource
    derivation_parameters: DerivationParameters
    capacity_limits: CapacityLimits
    coverage: MapCoverage
    nodes: tuple[FactNode, ...]
    edges: tuple[FactEdge, ...]
    cycle_groups: tuple[CycleGroup, ...]
    clusters: tuple[Cluster, ...]
    layers: tuple[Layer, ...]
    flows: tuple[StaticFlow, ...]
    tour: tuple[TourItem, ...]
    scope_contracts: tuple[ScopeContract, ...]
    evidence_snapshots: tuple[EvidenceSnapshot, ...]
    enrichments: tuple[ScopeEnrichment, ...]

    def __post_init__(self) -> None:
        if self.schema_version != KNOWLEDGE_MAP_SCHEMA_VERSION:
            raise ValueError("Knowledge Map schema version is unsupported")
        if (
            self.algorithm_id != KNOWLEDGE_MAP_ALGORITHM_ID
            or self.algorithm_version != KNOWLEDGE_MAP_ALGORITHM_VERSION
        ):
            raise ValueError("Knowledge Map algorithm identity is unsupported")
        if type(self.artifact_revision) is not int or self.artifact_revision < 1:
            raise ValueError("artifact revision must be positive")
        self._validate_collections()
        if self.deterministic_revision != self.compute_deterministic_revision():
            raise ValueError("deterministic revision does not match content")
        if self.semantic_revision != self.compute_semantic_revision():
            raise ValueError("semantic revision does not match content")
        if self.content_hash != self.compute_content_hash():
            raise ValueError("content hash does not match content")

    @classmethod
    def create_empty(cls, *, source: MapSource, budgets: MapBuildBudgets) -> Self:
        repository_node = FactNode(
            id=stable_id("repository", source.repository_fingerprint),
            kind="repository",
            origin="derived",
            name="repository",
            path=None,
            start_line=None,
            end_line=None,
            language=None,
            parent_id=None,
            parser_symbol_id=None,
        )
        return cls.create(
            artifact_revision=1,
            source=source,
            derivation_parameters=budgets.derivation_parameters(),
            capacity_limits=budgets.capacity_limits(),
            coverage=MapCoverage(included_nodes=1),
            nodes=(repository_node,),
        )

    @classmethod
    def create(
        cls,
        *,
        artifact_revision: int,
        source: MapSource,
        derivation_parameters: DerivationParameters,
        capacity_limits: CapacityLimits,
        coverage: MapCoverage,
        nodes: tuple[FactNode, ...] = (),
        edges: tuple[FactEdge, ...] = (),
        cycle_groups: tuple[CycleGroup, ...] = (),
        clusters: tuple[Cluster, ...] = (),
        layers: tuple[Layer, ...] = (),
        flows: tuple[StaticFlow, ...] = (),
        tour: tuple[TourItem, ...] = (),
        scope_contracts: tuple[ScopeContract, ...] = (),
        evidence_snapshots: tuple[EvidenceSnapshot, ...] = (),
        enrichments: tuple[ScopeEnrichment, ...] = (),
    ) -> Self:
        values: dict[str, Any] = {
            "schema_version": KNOWLEDGE_MAP_SCHEMA_VERSION,
            "algorithm_id": KNOWLEDGE_MAP_ALGORITHM_ID,
            "algorithm_version": KNOWLEDGE_MAP_ALGORITHM_VERSION,
            "artifact_revision": artifact_revision,
            "source": source,
            "derivation_parameters": derivation_parameters,
            "capacity_limits": capacity_limits,
            "coverage": coverage,
            "nodes": nodes,
            "edges": edges,
            "cycle_groups": cycle_groups,
            "clusters": clusters,
            "layers": layers,
            "flows": flows,
            "tour": tour,
            "scope_contracts": scope_contracts,
            "evidence_snapshots": evidence_snapshots,
            "enrichments": enrichments,
        }
        deterministic_revision = canonical_sha256(_deterministic_document(values))
        semantic_revision = canonical_sha256(
            {
                "enrichments": [item.to_document() for item in enrichments],
                "evidence_snapshots": [
                    item.to_document() for item in evidence_snapshots
                ],
            }
        )
        provisional = cls.__new__(cls)
        all_values = {
            **values,
            "content_hash": "",
            "deterministic_revision": deterministic_revision,
            "semantic_revision": semantic_revision,
        }
        for name, value in all_values.items():
            object.__setattr__(provisional, name, value)
        content_hash = provisional.compute_content_hash()
        return cls(
            content_hash=content_hash,
            **values,
            deterministic_revision=deterministic_revision,
            semantic_revision=semantic_revision,
        )

    def _validate_collections(self) -> None:
        for name in (
            "nodes",
            "edges",
            "cycle_groups",
            "clusters",
            "layers",
            "flows",
            "tour",
            "scope_contracts",
            "evidence_snapshots",
            "enrichments",
        ):
            values = cast(tuple[Any, ...], getattr(self, name))
            ids = tuple(
                cast(str, getattr(value, "id", getattr(value, "scope_id", "")))
                for value in values
            )
            if len(ids) != len(set(ids)):
                raise ValueError(f"{name} contains duplicate IDs")
        node_kind_order = {"repository": 0, "module": 1, "file": 2, "symbol": 3}

        def node_key(node: FactNode) -> tuple[object, ...]:
            if node.kind == "module":
                detail: tuple[object, ...] = (node.id,)
            elif node.kind == "file":
                detail = (node.path or "", node.id)
            elif node.kind == "symbol":
                detail = (node.path or "", node.start_line or 0, node.id)
            else:
                detail = (node.id,)
            return (node_kind_order[node.kind], *detail)

        if self.nodes != tuple(sorted(self.nodes, key=node_key)):
            raise ValueError("fact nodes are not in producer order")
        if self.edges != tuple(
            sorted(self.edges, key=lambda item: (item.origin, item.id))
        ):
            raise ValueError("fact edges are not in producer order")
        if self.cycle_groups != tuple(
            sorted(
                self.cycle_groups, key=lambda item: (item.member_module_ids, item.id)
            )
        ):
            raise ValueError("cycle groups are not in producer order")
        if self.clusters != tuple(
            sorted(self.clusters, key=lambda item: (item.member_node_ids, item.id))
        ):
            raise ValueError("clusters are not in producer order")
        if self.layers != tuple(
            sorted(self.layers, key=lambda item: (item.kind, item.id))
        ):
            raise ValueError("layers are not in producer order")
        if self.flows != tuple(
            sorted(self.flows, key=lambda item: (item.step_node_ids, item.id))
        ):
            raise ValueError("flows are not in producer order")
        if self.scope_contracts != tuple(
            sorted(
                self.scope_contracts, key=lambda item: (item.scope_kind, item.scope_id)
            )
        ):
            raise ValueError("scope contracts are not in producer order")
        if self.evidence_snapshots != tuple(
            sorted(self.evidence_snapshots, key=lambda item: item.scope_id)
        ) or self.enrichments != tuple(
            sorted(self.enrichments, key=lambda item: item.scope_id)
        ):
            raise ValueError("semantic sections are not in scope order")
        if self.tour != tuple(sorted(self.tour, key=lambda item: (item.rank, item.id))):
            raise ValueError("tour is not in rank order")
        for index, item in enumerate(self.tour):
            expected_next = (
                self.tour[index + 1].id if index + 1 < len(self.tour) else None
            )
            if item.next_item_id != expected_next:
                raise ValueError("tour adjacency is inconsistent")
        node_ids = {node.id for node in self.nodes}
        nodes_by_id = {node.id: node for node in self.nodes}
        repository_nodes = tuple(
            node for node in self.nodes if node.kind == "repository"
        )
        if len(repository_nodes) != 1:
            raise ValueError("Knowledge Map requires exactly one repository node")
        for node in self.nodes:
            if node.parent_id is not None and node.parent_id not in node_ids:
                raise ValueError("fact node has dangling parent")
            if node.kind == "module" and (
                node.parent_id is None
                or nodes_by_id[node.parent_id].kind != "repository"
            ):
                raise ValueError("module node must belong to the repository")
            if node.kind == "file" and (
                node.parent_id is None or nodes_by_id[node.parent_id].kind != "module"
            ):
                raise ValueError("file node must belong to a module")
            if node.kind == "symbol" and (
                node.parent_id is None or nodes_by_id[node.parent_id].kind != "file"
            ):
                raise ValueError("symbol node must belong to a file")
            if not set(node.resolution_candidate_ids) <= node_ids:
                raise ValueError("resolution candidate is not a persisted fact node")
        edge_ids = {edge.id for edge in self.edges}
        module_ids = {node.id for node in self.nodes if node.kind == "module"}
        cycle_group_ids = {group.id for group in self.cycle_groups}
        for group in self.cycle_groups:
            if not set(group.member_module_ids) <= module_ids:
                raise ValueError("cycle group has dangling module")
            if not set(group.edge_ids) <= edge_ids:
                raise ValueError("cycle group has dangling edge")
            for edge_id in group.edge_ids:
                edge = next(item for item in self.edges if item.id == edge_id)
                if (
                    edge.source_id not in group.member_module_ids
                    or edge.target_id not in group.member_module_ids
                    or edge.kind not in {"calls", "imports", "inherits"}
                ):
                    raise ValueError("cycle group contains a non-cycle dependency")
        for edge in self.edges:
            if edge.source_id not in node_ids or edge.target_id not in node_ids:
                raise ValueError("fact edge has dangling endpoint")
        cluster_ids = {item.id for item in self.clusters}
        flow_ids = {item.id for item in self.flows}
        tour_ids = {item.id for item in self.tour}
        for cluster in self.clusters:
            if not set(cluster.member_node_ids) <= node_ids:
                raise ValueError("cluster has dangling member")
            if any(
                nodes_by_id[item].kind != "file" for item in cluster.member_node_ids
            ):
                raise ValueError("cluster members must be file nodes")
            if not set(cluster.scc_ids) <= cycle_group_ids:
                raise ValueError("cluster has dangling cycle group")
            member_modules = {
                cast(str, nodes_by_id[item].parent_id)
                for item in cluster.member_node_ids
            }
            expected_cycle_ids = tuple(
                group.id
                for group in self.cycle_groups
                if set(group.member_module_ids) & member_modules
            )
            if cluster.scc_ids != expected_cycle_ids:
                raise ValueError("cluster cycle-group closure is inconsistent")
        for layer in self.layers:
            if not set(layer.member_node_ids) <= node_ids:
                raise ValueError("layer has dangling member")
        for flow in self.flows:
            if (
                flow.root_node_id not in node_ids
                or not set(flow.step_node_ids) <= node_ids
            ):
                raise ValueError("flow has dangling node")
            if not set(flow.edge_ids) <= edge_ids:
                raise ValueError("flow has dangling edge")
            for index, edge_id in enumerate(flow.edge_ids):
                edge = next(item for item in self.edges if item.id == edge_id)
                if (
                    edge.source_id != flow.step_node_ids[index]
                    or edge.target_id != flow.step_node_ids[index + 1]
                    or flow.transition_kinds[index] != edge.kind
                ):
                    raise ValueError("flow edge sequence is inconsistent")
                representative = flow.representative_relationship_ids[index]
                if representative not in edge.contributing_relationship_ids:
                    raise ValueError(
                        "flow representative occurrence is not an edge contributor"
                    )
        resolution_edges = tuple(
            edge for edge in self.edges if edge.kind == "resolves_to"
        )
        for node in self.nodes:
            matching = tuple(
                edge for edge in resolution_edges if edge.source_id == node.id
            )
            if node.resolution_status == "resolved":
                if (
                    not matching
                    or {edge.target_id for edge in matching}
                    != set(node.resolution_candidate_ids)
                    or any(edge.rule_id != node.resolution_rule_id for edge in matching)
                ):
                    raise ValueError("resolved reference traceability is inconsistent")
            elif matching:
                raise ValueError("non-resolved reference has a resolves-to edge")
        for item in self.tour:
            expected = {
                "node": node_ids,
                "cluster": cluster_ids,
                "flow": flow_ids,
            }.get(item.target_kind)
            if expected is None or item.target_id not in expected:
                raise ValueError("tour has dangling target")
            if item.next_item_id is not None and item.next_item_id not in tour_ids:
                raise ValueError("tour has dangling adjacency")
        scopes = {item.scope_id for item in self.scope_contracts}
        expected_scopes = cluster_ids | flow_ids | tour_ids
        if scopes != expected_scopes:
            raise ValueError(
                "scope contracts do not cover every semantic scope exactly"
            )
        expected_scope_values = _expected_scope_values(
            self.nodes,
            self.clusters,
            self.flows,
            self.tour,
        )
        for contract in self.scope_contracts:
            expected = {
                "cluster": cluster_ids,
                "flow": flow_ids,
                "tour": tour_ids,
            }[contract.scope_kind]
            if contract.scope_id not in expected:
                raise ValueError("scope contract has dangling scope")
            if not set(contract.allowed_fact_node_ids) <= node_ids:
                raise ValueError("scope contract has dangling fact node")
            if not set(contract.required_anchor_fact_node_ids) <= set(
                contract.allowed_fact_node_ids
            ):
                raise ValueError("scope contract anchor is not allowed")
            expected_allowed, expected_anchors = expected_scope_values[
                contract.scope_id
            ]
            if (
                contract.allowed_fact_node_ids != expected_allowed
                or contract.required_anchor_fact_node_ids != expected_anchors
            ):
                raise ValueError("scope contract expansion or anchors are inconsistent")
            expected_records = {
                "cluster": ("cluster_label", "concept"),
                "flow": ("flow_explanation", "concept"),
                "tour": ("reading_guidance", "concept"),
            }[contract.scope_kind]
            claim_permissions = {
                "cluster_label": (
                    "label",
                    "summary",
                    "responsibility",
                    "association",
                ),
                "flow_explanation": (
                    "label",
                    "summary",
                    "flow_explanation",
                    "association",
                ),
                "concept": (
                    "label",
                    "summary",
                    "concept_description",
                    "association",
                ),
                "reading_guidance": (
                    "label",
                    "summary",
                    "reading_guidance",
                    "association",
                ),
            }
            expected_claims = tuple(
                dict.fromkeys(
                    claim
                    for record_kind in expected_records
                    for claim in claim_permissions[record_kind]
                )
            )
            if (
                contract.allowed_record_kinds != expected_records
                or contract.allowed_claim_kinds != expected_claims
            ):
                raise ValueError("scope contract permissions do not match Schema 1.0")
        if any(item.scope_id not in scopes for item in self.evidence_snapshots):
            raise ValueError("Evidence snapshot has dangling scope")
        if any(item.scope_id not in scopes for item in self.enrichments):
            raise ValueError("enrichment has dangling scope")
        contracts = {item.scope_id: item for item in self.scope_contracts}
        snapshots = {item.scope_id: item for item in self.evidence_snapshots}
        for snapshot in self.evidence_snapshots:
            contract = contracts[snapshot.scope_id]
            if (
                snapshot.scope_kind != contract.scope_kind
                or snapshot.scope_contract_hash != contract.contract_hash
                or snapshot.deterministic_revision != self.deterministic_revision
                or snapshot.repository_fingerprint != self.source.repository_fingerprint
                or snapshot.index_build_id != self.source.index_build_id
                or snapshot.index_schema_version != self.source.index_schema_version
                or snapshot.source_control != self.source.source_control
                or snapshot.source_commit != self.source.source_commit
                or snapshot.source_dirty != self.source.source_dirty
            ):
                raise ValueError("Evidence snapshot identity is stale or inconsistent")
            if any(
                not set(reference.anchor_fact_node_ids)
                <= set(contract.allowed_fact_node_ids)
                for reference in snapshot.references
            ):
                raise ValueError("Evidence reference has a wrong-scope anchor")
        node_ids = {item.id for item in self.nodes}
        permissions = {
            "cluster_label": {
                "label",
                "summary",
                "responsibility",
                "association",
            },
            "flow_explanation": {
                "label",
                "summary",
                "flow_explanation",
                "association",
            },
            "concept": {
                "label",
                "summary",
                "concept_description",
                "association",
            },
            "reading_guidance": {
                "label",
                "summary",
                "reading_guidance",
                "association",
            },
        }
        for enrichment in self.enrichments:
            contract = contracts[enrichment.scope_id]
            evidence_snapshot = snapshots.get(enrichment.scope_id)
            if (
                evidence_snapshot is None
                or enrichment.scope_kind != contract.scope_kind
                or enrichment.scope_contract_hash != contract.contract_hash
                or enrichment.evidence_snapshot_hash != evidence_snapshot.snapshot_hash
            ):
                raise ValueError("enrichment identity is stale or inconsistent")
            evidence_ids = {item.evidence_id for item in evidence_snapshot.references}
            for record in enrichment.records:
                if record.kind not in contract.allowed_record_kinds:
                    raise ValueError("enrichment record is not allowed by its scope")
                for claim in record.claims:
                    if (
                        claim.kind not in contract.allowed_claim_kinds
                        or claim.kind not in permissions[record.kind]
                    ):
                        raise ValueError("enrichment claim is not allowed by its scope")
                    if (
                        not set(claim.fact_node_ids)
                        <= set(contract.allowed_fact_node_ids)
                        or not set(claim.related_node_ids) <= node_ids
                    ):
                        raise ValueError("enrichment has a wrong-scope node reference")
                    if not set(claim.evidence_ids) <= evidence_ids:
                        raise ValueError("enrichment has a dangling Evidence reference")
        _validate_artifact_capacity(self)
        if self.coverage.included_nodes != len(self.nodes):
            raise ValueError("coverage included-node count is inconsistent")
        if self.coverage.included_edges != len(self.edges):
            raise ValueError("coverage included-edge count is inconsistent")
        if self.coverage.included_clusters != len(self.clusters):
            raise ValueError("coverage included-cluster count is inconsistent")
        if self.coverage.included_flows != len(self.flows):
            raise ValueError("coverage included-flow count is inconsistent")
        if self.coverage.included_tour_items != len(self.tour):
            raise ValueError("coverage included-tour count is inconsistent")

    def compute_deterministic_revision(self) -> str:
        values = {
            "schema_version": self.schema_version,
            "algorithm_id": self.algorithm_id,
            "algorithm_version": self.algorithm_version,
            "source": self.source,
            "derivation_parameters": self.derivation_parameters,
            "coverage": self.coverage,
            "nodes": self.nodes,
            "edges": self.edges,
            "cycle_groups": self.cycle_groups,
            "clusters": self.clusters,
            "layers": self.layers,
            "flows": self.flows,
            "tour": self.tour,
            "scope_contracts": self.scope_contracts,
        }
        return canonical_sha256(_deterministic_document(values))

    def compute_semantic_revision(self) -> str:
        return canonical_sha256(
            {
                "enrichments": [item.to_document() for item in self.enrichments],
                "evidence_snapshots": [
                    item.to_document() for item in self.evidence_snapshots
                ],
            }
        )

    def compute_content_hash(self) -> str:
        document = self.to_document()
        del document["content_hash"]
        return canonical_sha256(document)

    def to_document(self) -> JsonObject:
        return {
            "algorithm_id": self.algorithm_id,
            "algorithm_version": self.algorithm_version,
            "artifact_revision": self.artifact_revision,
            "capacity_limits": self.capacity_limits.to_document(),
            "clusters": [item.to_document() for item in self.clusters],
            "content_hash": self.content_hash,
            "coverage": self.coverage.to_document(),
            "derivation_parameters": self.derivation_parameters.to_document(),
            "deterministic_revision": self.deterministic_revision,
            "edges": [item.to_document() for item in self.edges],
            "cycle_groups": [item.to_document() for item in self.cycle_groups],
            "enrichments": [item.to_document() for item in self.enrichments],
            "evidence_snapshots": [
                item.to_document() for item in self.evidence_snapshots
            ],
            "flows": [item.to_document() for item in self.flows],
            "layers": [item.to_document() for item in self.layers],
            "nodes": [item.to_document() for item in self.nodes],
            "schema_version": self.schema_version,
            "scope_contracts": [item.to_document() for item in self.scope_contracts],
            "semantic_revision": self.semantic_revision,
            "source": self.source.to_document(),
            "tour": [item.to_document() for item in self.tour],
        }

    @classmethod
    def from_document(cls, document: object) -> Self:
        value = _strict(document, _field_names(cls), "Knowledge Map")
        value["source"] = MapSource.from_document(value["source"])
        value["derivation_parameters"] = DerivationParameters.from_document(
            value["derivation_parameters"]
        )
        value["capacity_limits"] = CapacityLimits.from_document(
            value["capacity_limits"]
        )
        value["coverage"] = MapCoverage.from_document(value["coverage"])
        classes: tuple[tuple[str, type[Any]], ...] = (
            ("nodes", FactNode),
            ("edges", FactEdge),
            ("cycle_groups", CycleGroup),
            ("clusters", Cluster),
            ("layers", Layer),
            ("flows", StaticFlow),
            ("tour", TourItem),
            ("scope_contracts", ScopeContract),
            ("evidence_snapshots", EvidenceSnapshot),
            ("enrichments", ScopeEnrichment),
        )
        for name, model in classes:
            if type(value[name]) is not list:
                raise ValueError(f"Knowledge Map {name} must be an array")
            value[name] = tuple(model.from_document(item) for item in value[name])
        artifact = cls(**value)
        if (
            len(canonical_bytes(artifact.to_document())) + 1
            > artifact.capacity_limits.artifact_byte_budget
        ):
            raise ValueError("artifact byte capacity is exceeded")
        return artifact


def _deterministic_document(values: dict[str, Any]) -> JsonObject:
    names = (
        "schema_version",
        "algorithm_id",
        "algorithm_version",
        "source",
        "derivation_parameters",
        "coverage",
        "nodes",
        "edges",
        "cycle_groups",
        "clusters",
        "layers",
        "flows",
        "tour",
        "scope_contracts",
    )
    return cast(JsonObject, _json_value({name: values[name] for name in names}))


def _json_value(value: Any) -> Any:
    if hasattr(value, "to_document"):
        return value.to_document()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _dataclass_document(value: Any) -> JsonObject:
    return cast(
        JsonObject,
        {item.name: _json_value(getattr(value, item.name)) for item in fields(value)},
    )


def _field_names(model: type[Any]) -> set[str]:
    return {item.name for item in fields(model)}


def _strings(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not list or any(type(item) is not str for item in value):
        raise ValueError(f"{name} must be an array of strings")
    result = tuple(cast(list[str], value))
    _ordered_unique(result, name)
    return result


def _pairs(value: object, name: str) -> tuple[tuple[str, int], ...]:
    if type(value) is not list:
        raise ValueError(f"{name} must be an array")
    result: list[tuple[str, int]] = []
    for item in cast(list[object], value):
        if (
            type(item) is not list
            or len(cast(list[object], item)) != 2
            or type(cast(list[object], item)[0]) is not str
            or type(cast(list[object], item)[1]) is not int
        ):
            raise ValueError(f"{name} entries are invalid")
        pair = item
        result.append((pair[0], pair[1]))
    return tuple(result)


def _validate_artifact_capacity(artifact: KnowledgeMapArtifact) -> None:
    capacity = artifact.capacity_limits
    derivation = artifact.derivation_parameters
    if len(artifact.nodes) > derivation.node_budget:
        raise ValueError("fact node budget is exceeded")
    if len(artifact.edges) > derivation.edge_budget:
        raise ValueError("fact edge budget is exceeded")
    if len(artifact.clusters) > derivation.cluster_budget:
        raise ValueError("cluster budget is exceeded")
    if len(artifact.flows) > derivation.flow_budget:
        raise ValueError("flow budget is exceeded")
    if len(artifact.tour) > derivation.tour_budget:
        raise ValueError("tour budget is exceeded")
    if any(
        len(item.step_node_ids) > derivation.nodes_per_flow
        or len(item.edge_ids) > derivation.edges_per_flow
        or len(item.edge_ids) > derivation.flow_depth
        for item in artifact.flows
    ):
        raise ValueError("per-flow derivation budget is exceeded")
    if any(
        len(item.contributing_relationship_ids)
        > derivation.contributing_relationship_ids_per_edge
        for item in artifact.edges
    ):
        raise ValueError("relationship contributor budget is exceeded")
    if len(artifact.evidence_snapshots) > capacity.evidence_snapshots:
        raise ValueError("Evidence snapshot capacity is exceeded")
    if any(
        len(item.references) > capacity.evidence_references_per_snapshot
        for item in artifact.evidence_snapshots
    ):
        raise ValueError("Evidence reference capacity is exceeded")
    records = tuple(record for item in artifact.enrichments for record in item.records)
    if len(records) > capacity.enrichment_records or any(
        len(item.records) > capacity.records_per_scope for item in artifact.enrichments
    ):
        raise ValueError("enrichment record capacity is exceeded")
    claims = tuple(claim for record in records for claim in record.claims)
    if any(len(record.claims) > capacity.claims_per_record for record in records):
        raise ValueError("semantic claim capacity is exceeded")
    for name in ("fact_node_ids", "related_node_ids", "evidence_ids"):
        if any(
            len(getattr(claim, name)) > getattr(capacity, f"{name}_per_claim")
            for claim in claims
        ):
            raise ValueError(f"{name} capacity is exceeded")
    if any(
        item.canonical_input_bytes > capacity.enrichment_input_bytes
        for item in artifact.enrichments
    ):
        raise ValueError("enrichment input byte capacity is exceeded")


def _expected_scope_values(
    nodes: tuple[FactNode, ...],
    clusters: tuple[Cluster, ...],
    flows: tuple[StaticFlow, ...],
    tour: tuple[TourItem, ...],
) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    by_id = {node.id: node for node in nodes}

    def ancestors(node_id: str) -> tuple[str, ...]:
        values: list[str] = []
        current: str | None = node_id
        while current is not None and current in by_id:
            values.append(current)
            current = by_id[current].parent_id
        return tuple(values)

    result: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    for cluster in clusters:
        allowed: list[str] = []
        for member in cluster.member_node_ids:
            owned_symbols = tuple(
                node.id
                for node in nodes
                if node.kind == "symbol" and node.parent_id == member
            )
            if owned_symbols:
                for symbol_id in owned_symbols:
                    allowed.extend(ancestors(symbol_id))
            else:
                allowed.extend(ancestors(member))
        result[cluster.id] = (
            tuple(dict.fromkeys(allowed)),
            cluster.member_node_ids,
        )
    for flow in flows:
        allowed = []
        for node_id in flow.step_node_ids:
            allowed.extend(ancestors(node_id))
        result[flow.id] = (
            tuple(dict.fromkeys(allowed)),
            tuple(dict.fromkeys(flow.step_node_ids)),
        )
    for item in tour:
        if item.target_kind in {"cluster", "flow"}:
            result[item.id] = result[item.target_id]
        else:
            assert item.fact_node_id is not None
            result[item.id] = (
                tuple(dict.fromkeys(ancestors(item.fact_node_id))),
                (item.fact_node_id,),
            )
    return result
