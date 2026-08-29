"""Deterministic logical-ID composition for Wiki template contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from repo_dive.wiki.templates.models import (
    ComposedContract,
    ContractNode,
    Contribution,
    MergeOperation,
    TemplateIdentity,
)

if TYPE_CHECKING:
    from repo_dive.wiki.templates.registry import TemplateRegistry

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_PLACEHOLDER = re.compile(r"\{\{repo_dive:([a-z][a-z0-9_]*)\}\}")


def canonical_sha256(value: object) -> str:
    """Hash a JSON-compatible value using stable keys and semantic array order."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_composition_operations(
    base_nodes: tuple[ContractNode, ...], operations: tuple[MergeOperation, ...]
) -> None:
    """Validate merge targets, collisions, refinements, and dependency cycles."""
    _apply_operations(base_nodes, operations)


def compile_guidance(source: str, labels: dict[str, str]) -> str:
    """Resolve registered placeholders and remove generation-only comments."""

    def replace_placeholder(match: re.Match[str]) -> str:
        logical_id = match.group(1)
        try:
            return labels[logical_id]
        except KeyError as error:
            raise ValueError(
                f"guidance placeholder is unregistered: {logical_id}"
            ) from error

    body_lines = (
        line
        for line in source.splitlines()
        if not re.fullmatch(r"#{1,6}\s+\{\{repo_dive:[a-z][a-z0-9_]*\}\}\s*", line)
    )
    resolved = _PLACEHOLDER.sub(replace_placeholder, "\n".join(body_lines))
    if "{{" in resolved or "}}" in resolved:
        raise ValueError("guidance contains unregistered placeholder syntax")
    without_comments = _COMMENT.sub("", resolved)
    compiled = "\n".join(line.rstrip() for line in without_comments.splitlines())
    return compiled.strip() + "\n"


def compose_registry(
    registry: TemplateRegistry,
    primary_id: str,
    topology_id: str,
    facet_ids: tuple[str, ...],
    locale: str,
) -> ComposedContract:
    primary = _select(registry.primaries, primary_id, "primary")
    topology = _select(registry.topologies, topology_id, "topology")
    if locale not in registry.locale_ids:
        raise ValueError(f"unknown locale: {locale}")
    if len(facet_ids) != len(set(facet_ids)):
        raise ValueError("facet ids must not contain duplicates")
    unknown_facets = set(facet_ids) - set(registry.facet_ids)
    if unknown_facets:
        raise ValueError(f"unknown facet ids: {sorted(unknown_facets)}")
    selected_facets = tuple(
        contribution
        for contribution in registry.facets
        if contribution.id in set(facet_ids)
    )

    operations = (
        *topology.operations,
        *(operation for facet in selected_facets for operation in facet.operations),
    )
    nodes = _apply_operations(primary.nodes, operations)
    shell_ids = {
        node.logical_id
        for root in registry.framework_shell.nodes
        for node in root.walk()
    }
    composed_ids = {node.logical_id for root in nodes for node in root.walk()}
    collisions = shell_ids & composed_ids
    if collisions:
        raise ValueError(
            "framework shell and contribution logical ids collide: "
            f"{sorted(collisions)}"
        )
    catalog = next(item for item in registry.catalogs if item.locale == locale)
    labels = dict(catalog.labels)
    sources = registry.guidance_sources(primary, topology, selected_facets, locale)
    resolved_sources = tuple(_resolve_guidance(source, labels) for source in sources)
    annotated = "\n".join(source.rstrip() for source in resolved_sources) + "\n"
    compiled = "\n".join(
        compile_guidance(source, labels).rstrip() for source in sources
    )
    compiled += "\n"

    contract_document = {
        "framework_shell": registry.framework_shell.to_document(),
        "nodes": [node.to_document() for node in nodes],
        "primary": {"id": primary.id, "version": primary.version},
        "registry_version": registry.registry_version,
        "schema_version": registry.schema_version,
        "topology": {"id": topology.id, "version": topology.version},
        "facets": [
            {"id": facet.id, "version": facet.version} for facet in selected_facets
        ],
    }
    used_ids = {node.logical_id for root in nodes for node in root.walk()}
    used_ids.update(
        node.logical_id
        for root in registry.framework_shell.nodes
        for node in root.walk()
    )
    selected_labels = tuple(
        (key, value) for key, value in catalog.labels if key in used_ids
    )
    localized_document = {
        "annotated_guidance": annotated,
        "compiled_guidance": compiled,
        "contract_sha256": canonical_sha256(contract_document),
        "labels": dict(selected_labels),
        "locale": locale,
    }
    identity = TemplateIdentity(
        registry.schema_version,
        registry.registry_version,
        primary.id,
        primary.version,
        topology.id,
        topology.version,
        tuple(item.id for item in selected_facets),
        tuple(item.version for item in selected_facets),
        locale,
        canonical_sha256(contract_document),
        canonical_sha256(localized_document),
    )
    return ComposedContract(
        identity,
        registry.framework_shell,
        nodes,
        selected_labels,
        annotated,
        compiled,
    )


def _select(
    items: tuple[Contribution, ...], selected_id: str, dimension: str
) -> Contribution:
    for item in items:
        if item.id == selected_id:
            return item
    raise ValueError(f"unknown {dimension} id: {selected_id}")


def _resolve_guidance(source: str, labels: dict[str, str]) -> str:
    def replace_placeholder(match: re.Match[str]) -> str:
        try:
            return labels[match.group(1)]
        except KeyError as error:
            raise ValueError(
                f"guidance placeholder is unregistered: {match.group(1)}"
            ) from error

    return _PLACEHOLDER.sub(replace_placeholder, source)


def _apply_operations(
    base_nodes: tuple[ContractNode, ...], operations: tuple[MergeOperation, ...]
) -> tuple[ContractNode, ...]:
    existing_ids = {node.logical_id for root in base_nodes for node in root.walk()}
    inserted = [
        operation.node for operation in operations if operation.node is not None
    ]
    nested_ids = [
        descendant.logical_id for node in inserted for descendant in node.walk()
    ]
    if len(nested_ids) != len(set(nested_ids)) or existing_ids & set(nested_ids):
        raise ValueError("composition contains duplicate logical ids")

    inserted_owner = {
        descendant.logical_id: node.logical_id
        for node in inserted
        for descendant in node.walk()
    }
    dependencies = {
        operation.node.logical_id: inserted_owner[operation.target_id]
        for operation in operations
        if operation.node is not None and operation.target_id in inserted_owner
    }
    _reject_dependency_cycles(dependencies)

    pending = list(operations)
    nodes = base_nodes
    while pending:
        progressed = False
        for operation in tuple(pending):
            ids = {node.logical_id for root in nodes for node in root.walk()}
            if operation.target_id not in ids:
                continue
            nodes = _apply_one(nodes, operation)
            pending.remove(operation)
            progressed = True
        if not progressed:
            targets = sorted({operation.target_id for operation in pending})
            raise ValueError(f"composition target is missing: {targets}")
    return nodes


def _reject_dependency_cycles(dependencies: dict[str, str]) -> None:
    for start in dependencies:
        seen: set[str] = set()
        current = start
        while current in dependencies:
            if current in seen:
                raise ValueError("composition operation dependency cycle")
            seen.add(current)
            current = dependencies[current]


def _apply_one(
    roots: tuple[ContractNode, ...], operation: MergeOperation
) -> tuple[ContractNode, ...]:
    if operation.kind == "refine_existing":
        assert operation.refinement is not None
        refinement = operation.refinement
        return tuple(
            _map_node(
                root,
                operation.target_id,
                lambda node: node.refine(refinement),
            )
            for root in roots
        )
    assert operation.node is not None
    operation_node = operation.node
    if operation.kind == "append_to_slot":
        target = _find(roots, operation.target_id)
        if target.node_type != "extension_slot":
            raise ValueError("append_to_slot target must be an extension slot")
        if operation_node.node_type not in target.allowed_child_types:
            raise ValueError("extension slot rejects inserted node type")
        return tuple(
            _map_node(
                root,
                operation.target_id,
                lambda node: replace(node, children=(*node.children, operation_node)),
            )
            for root in roots
        )
    return _insert_sibling(roots, operation)


def _find(roots: tuple[ContractNode, ...], logical_id: str) -> ContractNode:
    for root in roots:
        for node in root.walk():
            if node.logical_id == logical_id:
                return node
    raise ValueError(f"composition target is missing: {logical_id}")


def _map_node(
    node: ContractNode,
    logical_id: str,
    transform: Callable[[ContractNode], ContractNode],
) -> ContractNode:
    if node.logical_id == logical_id:
        return transform(node)
    children = tuple(_map_node(child, logical_id, transform) for child in node.children)
    return replace(node, children=children) if children != node.children else node


def _insert_sibling(
    roots: tuple[ContractNode, ...], operation: MergeOperation
) -> tuple[ContractNode, ...]:
    assert operation.node is not None
    operation_node = operation.node

    def insert(
        items: tuple[ContractNode, ...],
    ) -> tuple[tuple[ContractNode, ...], bool]:
        result: list[ContractNode] = []
        found = False
        for item in items:
            if item.logical_id == operation.target_id:
                found = True
                if operation.kind == "insert_before":
                    result.append(operation_node)
                result.append(item)
                if operation.kind == "insert_after":
                    result.append(operation_node)
                continue
            children, child_found = insert(item.children)
            found = found or child_found
            result.append(replace(item, children=children) if child_found else item)
        return tuple(result), found

    composed, found = insert(roots)
    if not found:
        raise ValueError(f"composition target is missing: {operation.target_id}")
    return composed
