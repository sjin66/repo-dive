"""Deterministic retrieval over the private repository index."""

from repo_dive.retrieval.fusion import (
    FusionMetadata,
    FusionParameters,
    FusionResult,
    SearchHit,
    fuse_hits,
)
from repo_dive.retrieval.lexical import LexicalHit, search_lexical
from repo_dive.retrieval.structural import StructuralHit, search_structural

__all__ = [
    "FusionMetadata",
    "FusionParameters",
    "FusionResult",
    "LexicalHit",
    "SearchHit",
    "StructuralHit",
    "fuse_hits",
    "search_lexical",
    "search_structural",
]
