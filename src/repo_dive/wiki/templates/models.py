"""Immutable language-neutral contracts for bundled Wiki templates."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from repo_dive.schema import JsonObject, JsonValue

NodeType = Literal[
    "root",
    "contents",
    "section",
    "page",
    "heading",
    "paragraph",
    "list",
    "code_block",
    "table",
    "related_pages",
    "sources",
    "extension_slot",
]
NodeOwner = Literal["cli", "caller", "contract"]
ContributionDimension = Literal["primary", "topology", "facet"]
OperationKind = Literal[
    "insert_before", "insert_after", "append_to_slot", "refine_existing"
]
_NODE_TYPES = {
    "root",
    "contents",
    "section",
    "page",
    "heading",
    "paragraph",
    "list",
    "code_block",
    "table",
    "related_pages",
    "sources",
    "extension_slot",
}
_NODE_OWNERS = {"cli", "caller", "contract"}
_DIMENSIONS = {"primary", "topology", "facet"}
_OPERATION_KINDS = {
    "insert_before",
    "insert_after",
    "append_to_slot",
    "refine_existing",
}
_CANONICAL_LOCALES = {"en", "zh-CN", "ja"}


def _require_tuple(value: object, field_name: str) -> None:
    if type(value) is not tuple:
        raise ValueError(f"{field_name} must be an immutable tuple")


def is_logical_id(value: str) -> bool:
    """Return whether *value* is a stable lower-snake-case logical ID."""
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


@dataclass(frozen=True, slots=True)
class NodeConstraints:
    """Language-neutral cardinality and Markdown shape constraints."""

    required: bool
    min_count: int
    max_count: int
    heading_levels: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _require_tuple(self.heading_levels, "heading levels")
        if (
            type(self.required) is not bool
            or type(self.min_count) is not int
            or type(self.max_count) is not int
            or self.min_count < 0
            or self.max_count < self.min_count
        ):
            raise ValueError("node cardinality constraints must be valid")
        if self.required and self.min_count == 0:
            raise ValueError("required nodes must have positive minimum cardinality")
        if (
            any(type(level) is not int for level in self.heading_levels)
            or tuple(sorted(set(self.heading_levels))) != self.heading_levels
            or any(level < 1 or level > 6 for level in self.heading_levels)
        ):
            raise ValueError(
                "heading levels must be unique, ordered, and between 1 and 6"
            )

    def to_document(self) -> JsonObject:
        return {
            "heading_levels": list(self.heading_levels),
            "max_count": self.max_count,
            "min_count": self.min_count,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class ConstraintRefinement:
    """Optional constraint changes that may only narrow accepted documents."""

    required: bool | None = None
    min_count: int | None = None
    max_count: int | None = None
    heading_levels: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.required is not None and type(self.required) is not bool:
            raise ValueError("refinement required flag must be a boolean")
        if self.min_count is not None and (
            type(self.min_count) is not int or self.min_count < 0
        ):
            raise ValueError("refinement minimum must not be negative")
        if self.max_count is not None and (
            type(self.max_count) is not int or self.max_count < 0
        ):
            raise ValueError("refinement maximum must not be negative")
        if self.heading_levels is not None:
            _require_tuple(self.heading_levels, "refinement heading levels")
            if (
                any(type(level) is not int for level in self.heading_levels)
                or tuple(sorted(set(self.heading_levels))) != self.heading_levels
                or any(level < 1 or level > 6 for level in self.heading_levels)
            ):
                raise ValueError("refinement heading levels must be valid")


@dataclass(frozen=True, slots=True)
class ContractNode:
    """One recursively ordered node in the normalized template contract."""

    logical_id: str
    node_type: NodeType
    owner: NodeOwner
    constraints: NodeConstraints
    children: tuple[ContractNode, ...] = ()
    allowed_child_types: tuple[NodeType, ...] = ()

    def __post_init__(self) -> None:
        _require_tuple(self.children, "node children")
        _require_tuple(self.allowed_child_types, "allowed child types")
        if any(not isinstance(child, ContractNode) for child in self.children):
            raise ValueError("node children must contain only contract nodes")
        if not is_logical_id(self.logical_id):
            raise ValueError("node logical id must be lower snake case")
        if self.node_type not in _NODE_TYPES or self.owner not in _NODE_OWNERS:
            raise ValueError("node type and owner must be registered values")
        if len(self.allowed_child_types) != len(set(self.allowed_child_types)) or any(
            item not in _NODE_TYPES for item in self.allowed_child_types
        ):
            raise ValueError("allowed child types must be unique registered values")
        if self.node_type == "extension_slot":
            if self.owner != "contract" or not self.allowed_child_types:
                raise ValueError(
                    "extension slot nodes require contract ownership "
                    "and allowed children"
                )
            if (
                any(
                    child.node_type not in self.allowed_child_types
                    for child in self.children
                )
                or len(self.children) > self.constraints.max_count
            ):
                raise ValueError("extension slot children violate declared constraints")
        elif self.allowed_child_types:
            raise ValueError(
                "only extension slot nodes may declare allowed child types"
            )
        ids = [node.logical_id for node in self.walk()]
        if len(ids) != len(set(ids)):
            raise ValueError("contract node logical ids must be unique")

    def walk(self) -> tuple[ContractNode, ...]:
        return (
            self,
            *(descendant for child in self.children for descendant in child.walk()),
        )

    def refine(self, refinement: ConstraintRefinement) -> ContractNode:
        current = self.constraints
        required = (
            current.required if refinement.required is None else refinement.required
        )
        minimum = (
            current.min_count if refinement.min_count is None else refinement.min_count
        )
        maximum = (
            current.max_count if refinement.max_count is None else refinement.max_count
        )
        levels = (
            current.heading_levels
            if refinement.heading_levels is None
            else refinement.heading_levels
        )
        if (
            (current.required and not required)
            or minimum < current.min_count
            or maximum > current.max_count
            or (
                current.heading_levels
                and not set(levels) <= set(current.heading_levels)
            )
        ):
            raise ValueError("refinements may only tighten constraints")
        try:
            constraints = NodeConstraints(required, minimum, maximum, levels)
        except ValueError as error:
            raise ValueError("refinements may only tighten constraints") from error
        return replace(self, constraints=constraints)

    def to_document(self) -> JsonObject:
        return {
            "allowed_child_types": list(self.allowed_child_types),
            "children": [child.to_document() for child in self.children],
            "constraints": self.constraints.to_document(),
            "logical_id": self.logical_id,
            "node_type": self.node_type,
            "owner": self.owner,
        }


@dataclass(frozen=True, slots=True)
class MergeOperation:
    """A closed composition operation targeting a logical node ID."""

    kind: OperationKind
    target_id: str
    node: ContractNode | None = None
    refinement: ConstraintRefinement | None = None

    def __post_init__(self) -> None:
        if self.kind not in _OPERATION_KINDS:
            raise ValueError("operation kind is not registered")
        if not is_logical_id(self.target_id):
            raise ValueError("operation target logical id must be valid")
        if self.kind == "refine_existing":
            if self.refinement is None or self.node is not None:
                raise ValueError("refine_existing requires only a refinement")
        elif self.node is None or self.refinement is not None:
            raise ValueError("insertion operations require only a contract node")


@dataclass(frozen=True, slots=True)
class Contribution:
    """One primary base or topology/facet overlay contribution."""

    id: str
    dimension: ContributionDimension
    version: str
    nodes: tuple[ContractNode, ...] = ()
    operations: tuple[MergeOperation, ...] = ()

    def __post_init__(self) -> None:
        _require_tuple(self.nodes, "contribution nodes")
        _require_tuple(self.operations, "contribution operations")
        if (
            not is_logical_id(self.id)
            or self.dimension not in _DIMENSIONS
            or not self.version
            or self.version.strip() != self.version
        ):
            raise ValueError("contribution id and version must be valid")
        if self.dimension == "primary":
            if not self.nodes or self.operations:
                raise ValueError("primary contributions must define only base nodes")
        elif self.nodes or not self.operations:
            raise ValueError("overlay contributions must define only operations")
        ids = [node.logical_id for root in self.nodes for node in root.walk()]
        if len(ids) != len(set(ids)):
            raise ValueError("contribution logical ids must be unique")


@dataclass(frozen=True, slots=True)
class LocaleCatalog:
    """An exact locale key/value catalog with no fallback behavior."""

    locale: str
    labels: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        _require_tuple(self.labels, "locale labels")
        if self.locale not in _CANONICAL_LOCALES:
            raise ValueError("locale must be a canonical registered locale")
        if any(type(item) is not tuple or len(item) != 2 for item in self.labels):
            raise ValueError("locale labels must be immutable key/value pairs")
        keys = tuple(key for key, _ in self.labels)
        if len(keys) != len(set(keys)) or tuple(sorted(keys)) != keys:
            raise ValueError("locale keys must be unique and sorted")
        if any(
            not is_logical_id(key)
            or not isinstance(value, str)
            or not value
            or value.strip() != value
            for key, value in self.labels
        ):
            raise ValueError("locale keys and values must be valid non-empty strings")

    def resolve(self, key: str) -> str:
        try:
            return dict(self.labels)[key]
        except KeyError as error:
            raise ValueError(f"locale key is unavailable: {key}") from error

    def to_document(self) -> JsonObject:
        return {"locale": self.locale, "labels": dict(self.labels)}


@dataclass(frozen=True, slots=True)
class FrameworkShell:
    """Invariant CLI-owned Markdown nodes surrounding caller page bodies."""

    nodes: tuple[ContractNode, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.nodes, "framework shell nodes")
        walked = tuple(node for root in self.nodes for node in root.walk())
        if any(node.owner != "cli" for node in walked):
            raise ValueError("framework shell nodes must be CLI owned")
        ids = tuple(node.logical_id for node in walked)
        if len(ids) != len(set(ids)):
            raise ValueError("framework shell logical ids must be unique")
        if walked and sum(node.node_type == "root" for node in walked) != 1:
            raise ValueError("framework shell must contain exactly one root")

    def to_document(self) -> JsonObject:
        return {"nodes": [node.to_document() for node in self.nodes]}


@dataclass(frozen=True, slots=True)
class TemplateIdentity:
    schema_version: str
    registry_version: str
    primary_id: str
    primary_version: str
    topology_id: str
    topology_version: str
    facets: tuple[str, ...]
    facet_versions: tuple[str, ...]
    locale: str
    contract_sha256: str
    localized_sha256: str

    def __post_init__(self) -> None:
        _require_tuple(self.facets, "identity facets")
        _require_tuple(self.facet_versions, "identity facet versions")
        if len(self.facets) != len(self.facet_versions):
            raise ValueError("facet ids and versions must have equal lengths")
        if self.locale not in _CANONICAL_LOCALES:
            raise ValueError("locale must be a canonical registered locale")
        ids = (self.primary_id, self.topology_id, *self.facets)
        if any(not is_logical_id(item) for item in ids):
            raise ValueError("template identity ids must be valid logical ids")
        versions = (
            self.schema_version,
            self.registry_version,
            self.primary_version,
            self.topology_version,
            *self.facet_versions,
        )
        if any(not item or item.strip() != item for item in versions):
            raise ValueError("template identity versions must be non-empty")
        for digest in (self.contract_sha256, self.localized_sha256):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError("template identity hashes must be lowercase SHA-256")

    def to_document(self) -> JsonObject:
        return {
            "contract_sha256": self.contract_sha256,
            "facets": [
                {"id": id_, "version": version}
                for id_, version in zip(self.facets, self.facet_versions, strict=True)
            ],
            "locale": self.locale,
            "localized_sha256": self.localized_sha256,
            "primary_template_id": self.primary_id,
            "primary_template_version": self.primary_version,
            "registry_version": self.registry_version,
            "template_schema_version": self.schema_version,
            "topology": {"id": self.topology_id, "version": self.topology_version},
        }


@dataclass(frozen=True, slots=True)
class ComposedContract:
    """A complete normalized contract and resolved generation guidance."""

    identity: TemplateIdentity
    framework_shell: FrameworkShell
    nodes: tuple[ContractNode, ...]
    labels: tuple[tuple[str, str], ...]
    annotated_guidance: str
    compiled_guidance: str

    def __post_init__(self) -> None:
        _require_tuple(self.nodes, "composed contract nodes")
        _require_tuple(self.labels, "composed contract labels")
        keys = tuple(key for key, _ in self.labels)
        if len(keys) != len(set(keys)) or tuple(sorted(keys)) != keys:
            raise ValueError("composed contract labels must be unique and sorted")
        ids = tuple(node.logical_id for root in self.nodes for node in root.walk())
        if len(ids) != len(set(ids)):
            raise ValueError("composed contract logical ids must be unique")
        if (
            not self.compiled_guidance
            or "<!--" in self.compiled_guidance
            or "{{" in self.compiled_guidance
            or "}}" in self.compiled_guidance
        ):
            raise ValueError(
                "compiled guidance must contain only resolved output guidance"
            )

    def to_document(self) -> JsonObject:
        document: dict[str, JsonValue] = {
            "annotated_guidance": self.annotated_guidance,
            "compiled_guidance": self.compiled_guidance,
            "framework_shell": self.framework_shell.to_document(),
            "identity": self.identity.to_document(),
            "labels": dict(self.labels),
            "nodes": [node.to_document() for node in self.nodes],
        }
        return document
