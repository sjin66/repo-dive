"""Deterministic retrieval over the private repository index."""

from repo_dive.retrieval.lexical import LexicalHit, search_lexical
from repo_dive.retrieval.structural import StructuralHit, search_structural

__all__ = [
    "LexicalHit",
    "StructuralHit",
    "search_lexical",
    "search_structural",
]
