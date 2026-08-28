"""Explicit optional provider adapters."""

from repo_dive.providers.embeddings import (
    EmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
)

__all__ = [
    "EmbeddingProvider",
    "SentenceTransformersEmbeddingProvider",
]
