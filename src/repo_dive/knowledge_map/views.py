"""Pure bounded projections from one complete Knowledge Map snapshot."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from repo_dive.knowledge_map.models import KnowledgeMapArtifact
from repo_dive.schema import JsonObject, JsonValue


def project_architecture(
    artifact: KnowledgeMapArtifact, *, max_results: int
) -> JsonObject:
    """Project layers, clusters, modules, and aggregate dependencies."""
    labels = _presentation_labels(artifact)
    records: list[JsonValue] = []
    records.extend(
        _labeled({"record_kind": "layer", **item.to_document()}, item.id, labels)
        for item in artifact.layers
    )
    records.extend(
        _labeled({"record_kind": "cluster", **item.to_document()}, item.id, labels)
        for item in artifact.clusters
    )
    records.extend(
        {"record_kind": "cycle_group", **item.to_document()}
        for item in artifact.cycle_groups
    )
    records.extend(
        _labeled({"record_kind": "module", **item.to_document()}, item.id, labels)
        for item in artifact.nodes
        if item.kind == "module"
    )
    records.extend(
        {"record_kind": "dependency", **item.to_document()}
        for item in artifact.edges
        if item.origin == "derived"
        and item.rule_id is not None
        and item.rule_id.startswith("aggregate_")
    )
    return _projection(artifact, records, max_results)


def project_flows(artifact: KnowledgeMapArtifact, *, max_results: int) -> JsonObject:
    labels = _presentation_labels(artifact)
    return _projection(
        artifact,
        (_labeled(item.to_document(), item.id, labels) for item in artifact.flows),
        max_results,
    )


def project_tour(artifact: KnowledgeMapArtifact, *, max_results: int) -> JsonObject:
    labels = _presentation_labels(artifact)
    return _projection(
        artifact,
        (_labeled(item.to_document(), item.id, labels) for item in artifact.tour),
        max_results,
    )


def _presentation_labels(artifact: KnowledgeMapArtifact) -> dict[str, str]:
    labels: dict[str, str] = {}
    for enrichment in artifact.enrichments:
        for record in enrichment.records:
            for claim in record.claims:
                if claim.kind != "label":
                    continue
                labels.setdefault(enrichment.scope_id, claim.text)
                for node_id in claim.fact_node_ids:
                    labels.setdefault(node_id, claim.text)
    return labels


def _labeled(document: JsonObject, item_id: str, labels: dict[str, str]) -> JsonObject:
    label = labels.get(item_id)
    if label is None:
        return document
    return {**document, "presentation_label": label}


def _projection(
    artifact: KnowledgeMapArtifact,
    values: Iterable[JsonValue],
    max_results: int,
) -> JsonObject:
    if max_results <= 0:
        raise ValueError("max_results must be positive")
    all_values = tuple(values)
    included = all_values[:max_results]
    return cast(
        JsonObject,
        {
            "artifact_revision": artifact.artifact_revision,
            "coverage": artifact.coverage.to_document(),
            "deterministic_revision": artifact.deterministic_revision,
            "included_count": len(included),
            "items": list(included),
            "omitted_count": len(all_values) - len(included),
            "semantic_available": bool(artifact.enrichments),
            "semantic_revision": artifact.semantic_revision,
            "truncated": len(included) < len(all_values),
        },
    )
