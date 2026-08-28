"""Explicit CLI selection for the optional local embedding provider."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repo_dive.errors import RepoDiveError
from repo_dive.indexing.vectors import EmbeddingIdentity
from repo_dive.providers.embeddings import (
    EmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
    VectorFailurePolicy,
)


@dataclass(frozen=True, slots=True)
class EmbeddingSelection:
    """One explicit provider request, including safe degraded setup state."""

    requested: bool
    failure_policy: VectorFailurePolicy
    provider: EmbeddingProvider | None = None
    error_code: str | None = None

    @property
    def identity(self) -> EmbeddingIdentity | None:
        return self.provider.identity if self.provider is not None else None

    @property
    def warning(self) -> str | None:
        if self.error_code is None:
            return None
        return f"vector_degraded:{self.error_code}"


def select_local_embedding_provider(
    model_path: str | Path | None,
    *,
    failure_policy: VectorFailurePolicy,
) -> EmbeddingSelection:
    """Construct the requested local provider or record a safe degraded state."""
    if failure_policy not in ("strict", "degraded"):
        raise ValueError("failure_policy must be strict or degraded")
    if model_path is None:
        return EmbeddingSelection(
            requested=False,
            failure_policy=failure_policy,
        )
    try:
        provider = SentenceTransformersEmbeddingProvider(model_path)
    except RepoDiveError as error:
        if failure_policy == "strict":
            raise
        return EmbeddingSelection(
            requested=True,
            failure_policy=failure_policy,
            error_code=error.code,
        )
    return EmbeddingSelection(
        requested=True,
        failure_policy=failure_policy,
        provider=provider,
    )


__all__ = ["EmbeddingSelection", "select_local_embedding_provider"]
