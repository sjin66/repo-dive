"""Explicit optional provider adapters."""

from repo_dive.providers.embeddings import (
    EmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
    VectorFailurePolicy,
)

__all__ = [
    "EmbeddingProvider",
    "SentenceTransformersEmbeddingProvider",
    "VectorFailurePolicy",
]
