"""Conservative deterministic resolution for supported Python references."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from repo_dive.parsing.models import Relationship, Symbol

ResolutionStatus = Literal["resolved", "ambiguous", "unresolved", "unsupported"]


@dataclass(frozen=True, slots=True)
class ReferenceResolution:
    relationship_id: str
    reference_symbol_id: str
    status: ResolutionStatus
    resolved_symbol_id: str | None
    candidate_symbol_ids: tuple[str, ...]
    rule_id: str | None
    candidates_truncated: bool

    def __post_init__(self) -> None:
        if not self.relationship_id or not self.reference_symbol_id:
            raise ValueError("resolution identities must not be empty")
        if self.status not in {"resolved", "ambiguous", "unresolved", "unsupported"}:
            raise ValueError("resolution status is invalid")
        if len(self.candidate_symbol_ids) != len(set(self.candidate_symbol_ids)):
            raise ValueError("resolution candidates must be unique")
        if self.status == "resolved" and (
            self.resolved_symbol_id is None
            or self.candidate_symbol_ids != (self.resolved_symbol_id,)
            or self.rule_id is None
        ):
            raise ValueError("resolved reference metadata is inconsistent")
        if self.status != "resolved" and self.resolved_symbol_id is not None:
            raise ValueError("non-resolved reference cannot select a target")


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    relationships: tuple[Relationship, ...]
    resolutions: tuple[ReferenceResolution, ...]

    def resolved_target(self, relationship: Relationship) -> str:
        for resolution in self.resolutions:
            if (
                resolution.relationship_id == relationship.id
                and resolution.resolved_symbol_id is not None
            ):
                return resolution.resolved_symbol_id
        return relationship.target_id


def resolve_python_references(
    symbols: tuple[Symbol, ...],
    relationships: tuple[Relationship, ...],
    *,
    candidate_budget: int,
) -> ResolutionResult:
    """Resolve exact or uniquely constrained Python names; never guess ties."""
    if candidate_budget <= 0:
        raise ValueError("candidate budget must be positive")
    by_id = {symbol.id: symbol for symbol in symbols}
    definitions = tuple(
        symbol for symbol in symbols if symbol.kind not in {"reference", "import"}
    )
    by_qualified: dict[str, list[Symbol]] = {}
    by_short: dict[str, list[Symbol]] = {}
    for symbol in definitions:
        by_qualified.setdefault(symbol.qualified_name, []).append(symbol)
        by_short.setdefault(symbol.name, []).append(symbol)

    resolutions: list[ReferenceResolution] = []
    for relationship in relationships:
        target = by_id.get(relationship.target_id)
        if target is None or target.kind not in {"reference", "import"}:
            continue
        if not relationship.path.endswith(".py"):
            resolutions.append(
                _resolution(
                    relationship, target, "unsupported", (), None, candidate_budget
                )
            )
            continue
        source = by_id.get(relationship.source_id)
        qualified_names = _qualified_candidates(target.qualified_name, source)
        exact = tuple(
            sorted(
                {
                    candidate.id: candidate
                    for qualified_name in qualified_names
                    for candidate in by_qualified.get(qualified_name, ())
                }.values(),
                key=_symbol_key,
            )
        )
        if len(exact) == 1:
            resolutions.append(
                _resolution(
                    relationship,
                    target,
                    "resolved",
                    exact,
                    (
                        "python_relative_qualified_v1"
                        if qualified_names[0] != target.qualified_name
                        else "python_exact_qualified_v1"
                    ),
                    candidate_budget,
                )
            )
            continue
        candidates = exact or tuple(
            sorted(
                (
                    candidate
                    for candidate in by_short.get(target.name, ())
                    if source is not None
                    and PurePosixPath(candidate.path).parent
                    == PurePosixPath(source.path).parent
                ),
                key=_symbol_key,
            )
        )
        if len(candidates) == 1:
            status: ResolutionStatus = "resolved"
            rule = "python_unique_package_short_name_v1"
        elif candidates:
            status = "ambiguous"
            rule = "python_ambiguous_v1"
        else:
            status = "unresolved"
            rule = None
        resolutions.append(
            _resolution(
                relationship,
                target,
                status,
                candidates,
                rule,
                candidate_budget,
            )
        )
    return ResolutionResult(
        relationships=relationships,
        resolutions=tuple(sorted(resolutions, key=lambda item: item.relationship_id)),
    )


def _resolution(
    relationship: Relationship,
    target: Symbol,
    status: ResolutionStatus,
    candidates: tuple[Symbol, ...],
    rule_id: str | None,
    budget: int,
) -> ReferenceResolution:
    included = candidates[:budget]
    return ReferenceResolution(
        relationship_id=relationship.id,
        reference_symbol_id=target.id,
        status=status,
        resolved_symbol_id=included[0].id if status == "resolved" else None,
        candidate_symbol_ids=tuple(item.id for item in included),
        rule_id=rule_id,
        candidates_truncated=len(candidates) > len(included),
    )


def _symbol_key(symbol: Symbol) -> tuple[str, int, int, str]:
    return (symbol.path, symbol.start_line, symbol.end_line, symbol.id)


def _qualified_candidates(value: str, source: Symbol | None) -> tuple[str, ...]:
    if not value.startswith(".") or source is None:
        return (value,)
    level = len(value) - len(value.lstrip("."))
    suffix = value[level:]
    package = list(PurePosixPath(source.path).with_suffix("").parts[:-1])
    remove = max(0, level - 1)
    if remove > len(package):
        return (value,)
    base = package[: len(package) - remove]
    normalized = ".".join((*base, suffix)) if suffix else ".".join(base)
    return (normalized, value)
