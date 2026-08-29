"""Pure deterministic matching, scoring, and selection."""

from __future__ import annotations

import json
import tomllib
from fnmatch import fnmatchcase
from typing import cast

from repo_dive.classification.models import (
    MAX_MANIFEST_BYTES,
    ClassificationObservation,
    ClassificationResult,
    FallbackReason,
    IndexSnapshot,
    MatchedSignal,
    ScoredPrimary,
    ScoredTaxon,
    SelectionSource,
)
from repo_dive.classification.registry import (
    BUILTIN_REGISTRY,
    ExactPath,
    LanguageCount,
    LanguageRatio,
    NamedManifestKeyValue,
    PathGlob,
    RuleRegistry,
    SignalRule,
)
from repo_dive.errors import InvocationError


class ClassificationError(InvocationError):
    """A stable validation failure at the classification domain boundary."""


class ClassificationService:
    """Classify one immutable current-index snapshot using a fixed registry."""

    def __init__(self, registry: RuleRegistry = BUILTIN_REGISTRY) -> None:
        self._registry = registry

    def classify(
        self, snapshot: IndexSnapshot, *, override: str | None = None
    ) -> ClassificationResult:
        primary_ids = {item.id for item in self._registry.primaries}
        if override is not None and override not in primary_ids:
            raise ClassificationError(
                "classification_override_unknown",
                "Classification template override is not registered.",
                details={"override": override},
            )

        manifests, observations = _parse_named_manifests(snapshot, self._registry)
        scores = {
            "primary": {item.id: 0 for item in self._registry.primaries},
            "topology": {item.id: 0 for item in self._registry.topologies},
            "facet": {item.id: 0 for item in self._registry.facets},
        }
        matched: list[MatchedSignal] = []
        for rule in self._registry.signals:
            paths = _match(rule, snapshot, manifests)
            if paths:
                scores[rule.dimension][rule.target_id] += rule.weight
                matched.append(MatchedSignal(rule.id, rule.weight, paths))

        detected, fallback_reason = self._select_primary(scores["primary"])
        topology = self._select_topology(scores["topology"])
        facets = tuple(
            ScoredTaxon(taxon.id, scores["facet"][taxon.id])
            for taxon in self._registry.facets
            if scores["facet"][taxon.id] >= taxon.threshold
        )
        if override is None:
            effective = detected
            source: SelectionSource = (
                "fallback" if fallback_reason is not None else "automatic"
            )
        else:
            effective = ScoredPrimary(override, scores["primary"][override], "override")
            source = "override"
        return ClassificationResult(
            repository_fingerprint=snapshot.repository_fingerprint,
            index_build_id=snapshot.index_build_id,
            selection_source=source,
            detected_primary=detected,
            effective_primary=effective,
            topology=topology,
            facets=facets,
            matched_signals=tuple(matched),
            observations=observations,
            template_override=override,
            fallback_reason=fallback_reason,
        )

    def _select_primary(
        self, scores: dict[str, int]
    ) -> tuple[ScoredPrimary, FallbackReason | None]:
        candidates = [
            item for item in self._registry.primaries if item.id != "general_mixed"
        ]
        ranked = sorted(candidates, key=lambda item: (-scores[item.id], item.id))
        top = ranked[0]
        runner_up_score = scores[ranked[1].id] if len(ranked) > 1 else 0
        reason: FallbackReason | None = None
        if scores[top.id] < top.threshold:
            reason = "below_threshold"
        elif scores[top.id] == runner_up_score:
            reason = "tied"
        elif scores[top.id] - runner_up_score < self._registry.primary_margin:
            reason = "ambiguous"
        if reason is not None:
            return ScoredPrimary("general_mixed", scores[top.id], "fallback"), reason
        return ScoredPrimary(top.id, scores[top.id], "high"), None

    def _select_topology(self, scores: dict[str, int]) -> ScoredTaxon:
        overlays = [
            item for item in self._registry.topologies if item.id != "single_project"
        ]
        eligible = [item for item in overlays if scores[item.id] >= item.threshold]
        if not eligible:
            return ScoredTaxon("single_project", scores.get("single_project", 0))
        best_score = max(scores[item.id] for item in eligible)
        best = [item for item in eligible if scores[item.id] == best_score]
        if len(best) != 1:
            return ScoredTaxon("single_project", 0)
        return ScoredTaxon(best[0].id, best_score)


def _match(
    rule: SignalRule,
    snapshot: IndexSnapshot,
    manifests: dict[str, object],
) -> tuple[str, ...]:
    matcher = rule.matcher
    paths = tuple(item.path for item in snapshot.files)
    if isinstance(matcher, ExactPath):
        return (matcher.path,) if matcher.path in paths else ()
    if isinstance(matcher, PathGlob):
        matched = tuple(path for path in paths if fnmatchcase(path, matcher.pattern))
        return matched if len(matched) >= matcher.min_count else ()
    if isinstance(matcher, LanguageCount):
        matched = tuple(
            item.path for item in snapshot.files if item.language == matcher.language
        )
        return matched if len(matched) >= matcher.minimum else ()
    if isinstance(matcher, LanguageRatio):
        matched = tuple(
            item.path for item in snapshot.files if item.language == matcher.language
        )
        total = len(snapshot.files)
        if total < matcher.minimum_files:
            return ()
        return (
            matched
            if len(matched) * matcher.denominator >= total * matcher.numerator
            else ()
        )
    document = manifests.get(matcher.path)
    if document is None:
        return ()
    value = _nested_value(document, matcher.key)
    if value is _MISSING:
        return ()
    if matcher.present:
        return (matcher.path,)
    if matcher.contains is not None and isinstance(value, (list, dict)):
        return (matcher.path,) if matcher.contains in value else ()
    return (matcher.path,) if value == matcher.equals else ()


_MISSING = object()


def _nested_value(document: object, key: tuple[str, ...]) -> object:
    value = document
    for part in key:
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = cast(dict[str, object], value)[part]
    return value


def _parse_named_manifests(
    snapshot: IndexSnapshot, registry: RuleRegistry
) -> tuple[dict[str, object], tuple[ClassificationObservation, ...]]:
    named_paths = {
        rule.matcher.path
        for rule in registry.signals
        if isinstance(rule.matcher, NamedManifestKeyValue)
    }
    manifests: dict[str, object] = {}
    observations: list[ClassificationObservation] = []
    for item in snapshot.files:
        if item.path not in named_paths:
            continue
        if item.size_bytes > MAX_MANIFEST_BYTES or (
            item.text is not None
            and len(item.text.encode("utf-8", errors="surrogatepass"))
            > MAX_MANIFEST_BYTES
        ):
            observations.append(
                ClassificationObservation("manifest_oversized", item.path)
            )
            continue
        if item.text is None:
            continue
        try:
            if item.path.endswith(".json"):
                value = json.loads(
                    item.text,
                    object_pairs_hook=_unique_json_object,
                    parse_constant=_reject_json_constant,
                )
            elif item.path.endswith(".toml"):
                value = tomllib.loads(item.text)
            else:
                continue
            if not isinstance(value, dict):
                raise ValueError
            manifests[item.path] = value
        except (
            UnicodeError,
            json.JSONDecodeError,
            tomllib.TOMLDecodeError,
            RecursionError,
            ValueError,
        ):
            observations.append(
                ClassificationObservation("manifest_malformed", item.path)
            )
    return manifests, tuple(observations)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")
