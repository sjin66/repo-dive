"""Built-in deterministic multilingual Wiki template contracts."""

from repo_dive.wiki.templates.models import (
    ComposedContract,
    ConstraintRefinement,
    ContractNode,
    Contribution,
    FrameworkShell,
    LocaleCatalog,
    MergeOperation,
    NodeConstraints,
    TemplateIdentity,
)
from repo_dive.wiki.templates.registry import (
    SUPPORTED_LOCALES,
    TemplateRegistry,
    enumerate_resource_names,
    expected_resource_names,
    load_builtin_registry,
)


def compose_template(
    primary_id: str, topology_id: str, facet_ids: tuple[str, ...], locale: str
) -> ComposedContract:
    """Compose one closed built-in contract with exact locale resolution."""
    return load_builtin_registry().compose(primary_id, topology_id, facet_ids, locale)


__all__ = [
    "SUPPORTED_LOCALES",
    "ComposedContract",
    "ConstraintRefinement",
    "ContractNode",
    "Contribution",
    "FrameworkShell",
    "LocaleCatalog",
    "MergeOperation",
    "NodeConstraints",
    "TemplateIdentity",
    "TemplateRegistry",
    "compose_template",
    "enumerate_resource_names",
    "expected_resource_names",
    "load_builtin_registry",
]
