"""Deterministic repository classification domain package."""

from repo_dive.classification.adapter import snapshot_from_published_index
from repo_dive.classification.models import (
    ClassificationResult,
    IndexedFile,
    IndexSnapshot,
)
from repo_dive.classification.registry import (
    BUILTIN_REGISTRY,
    FACET_IDS,
    PRIMARY_IDS,
    TOPOLOGY_IDS,
)
from repo_dive.classification.service import ClassificationError, ClassificationService

__all__ = [
    "BUILTIN_REGISTRY",
    "FACET_IDS",
    "PRIMARY_IDS",
    "TOPOLOGY_IDS",
    "ClassificationError",
    "ClassificationResult",
    "ClassificationService",
    "IndexSnapshot",
    "IndexedFile",
    "snapshot_from_published_index",
]
