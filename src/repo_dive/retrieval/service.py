"""Read-only orchestration over one validated published repository index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from repo_dive.errors import InternalOperationError, RepoDiveError, RepositoryError
from repo_dive.indexing.graph import SymbolGraph
from repo_dive.indexing.service import load_published_index
from repo_dive.indexing.store import IndexStore
from repo_dive.indexing.vectors import EmbeddingIdentity
from repo_dive.parsing.models import Chunk, Symbol
from repo_dive.providers.embeddings import EmbeddingProvider, VectorFailurePolicy
from repo_dive.retrieval.fusion import FusionParameters, FusionResult, fuse_hits
from repo_dive.retrieval.lexical import search_lexical
from repo_dive.retrieval.structural import search_structural
from repo_dive.retrieval.vector import VectorHit, search_vector

DEFAULT_MAX_RESULTS = 10
MAX_RESULTS = 50
CANDIDATE_MULTIPLIER = 4
MAX_CANDIDATES = MAX_RESULTS * CANDIDATE_MULTIPLIER
VectorSearchStatus = Literal["ready", "degraded"]


@dataclass(frozen=True, slots=True)
class RepositorySearchResult:
    """A reproducible fused result plus source symbols needed for formatting."""

    repository: Path
    build_id: str
    fusion: FusionResult
    symbols: tuple[Symbol, ...]
    vector: VectorSearchResult | None = None


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    """Observable model identity, cost, and failure state for vector retrieval."""

    status: VectorSearchStatus
    failure_policy: VectorFailurePolicy
    identity: EmbeddingIdentity
    indexed_chunks: int
    query_embeddings: int
    error_code: str | None = None


def search_repository(
    repository: str | Path,
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    embedding_provider: EmbeddingProvider | None = None,
    vector_failure: VectorFailurePolicy = "strict",
) -> RepositorySearchResult:
    """Search a current index without mutating repository-owned artifacts."""
    if not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"max_results must be from 1 to {MAX_RESULTS}")
    if vector_failure not in ("strict", "degraded"):
        raise ValueError("vector_failure must be strict or degraded")

    published = load_published_index(repository)
    candidate_limit = min(max_results * CANDIDATE_MULTIPLIER, MAX_CANDIDATES)
    vector_result: VectorSearchResult | None = None
    with IndexStore.open_readonly(published.database) as store:
        chunks = store.get_chunks()
        bm25_index = store.get_bm25_index()
        if bm25_index is None:
            raise RepositoryError(
                "index_incomplete",
                "Repository index does not contain lexical search data.",
                details={"build_id": published.manifest.build_id},
            )
        lexical_hits = search_lexical(
            query,
            index=bm25_index,
            chunks=chunks,
            max_results=candidate_limit,
        )
        structural_hits = search_structural(
            query,
            graph=SymbolGraph(store),
            chunks=chunks,
            max_results=candidate_limit,
            max_nodes=MAX_CANDIDATES,
            max_edges=MAX_CANDIDATES * 4,
        )
        vector_hits: tuple[VectorHit, ...] = ()
        if embedding_provider is not None:
            vector_hits, vector_result = _search_vectors(
                query=query,
                provider=embedding_provider,
                failure_policy=vector_failure,
                manifest_identity=published.manifest.embedding,
                store=store,
                chunks=chunks,
                max_results=candidate_limit,
            )
        fusion = fuse_hits(
            lexical_hits=lexical_hits,
            structural_hits=structural_hits,
            vector_hits=vector_hits,
            parameters=(
                FusionParameters(vector_weight=1.0)
                if vector_result is not None and vector_result.status == "ready"
                else None
            ),
            max_results=max_results,
        )
        symbol_ids = tuple(
            dict.fromkeys(
                hit.chunk.symbol_id
                for hit in fusion.hits
                if hit.chunk.symbol_id is not None
            )
        )
        symbols = store.get_symbols_by_id(symbol_ids)

    return RepositorySearchResult(
        repository=published.repository,
        build_id=published.manifest.build_id,
        fusion=fusion,
        symbols=symbols,
        vector=vector_result,
    )


def _search_vectors(
    *,
    query: str,
    provider: EmbeddingProvider,
    failure_policy: VectorFailurePolicy,
    manifest_identity: EmbeddingIdentity | None,
    store: IndexStore,
    chunks: tuple[Chunk, ...],
    max_results: int,
) -> tuple[tuple[VectorHit, ...], VectorSearchResult]:
    identity = provider.identity
    indexed_chunks = 0
    query_embeddings = 0
    try:
        if manifest_identity is None:
            raise RepositoryError(
                "index_vector_not_found",
                "Repository index does not contain vectors for the requested model.",
            )
        if manifest_identity != identity:
            raise RepositoryError(
                "index_vector_identity_mismatch",
                "Repository index vectors use a different embedding model.",
            )
        vectors = store.get_vector_index(identity)
        indexed_chunks = len(vectors)
        if indexed_chunks != len(chunks):
            raise RepositoryError(
                "index_vector_incomplete",
                "Repository vector index is incomplete; run `repo-dive index` again.",
            )
        query_vectors = provider.embed((query,))
        if len(query_vectors) != 1:
            raise ValueError("embedding provider did not return one query vector")
        query_embeddings = 1
        vector_hits = search_vector(
            query_vectors[0],
            identity=identity,
            vectors=vectors,
            chunks=chunks,
            max_results=max_results,
        )
    except Exception as error:
        if failure_policy == "strict":
            if isinstance(error, RepoDiveError):
                raise
            raise InternalOperationError(
                "vector_search_failed",
                "Could not search the local vector index.",
            ) from error
        return (
            (),
            VectorSearchResult(
                status="degraded",
                failure_policy=failure_policy,
                identity=identity,
                indexed_chunks=indexed_chunks,
                query_embeddings=query_embeddings,
                error_code=(
                    error.code
                    if isinstance(error, RepoDiveError)
                    else "vector_search_failed"
                ),
            ),
        )
    return (
        vector_hits,
        VectorSearchResult(
            status="ready",
            failure_policy=failure_policy,
            identity=identity,
            indexed_chunks=indexed_chunks,
            query_embeddings=query_embeddings,
        ),
    )


__all__ = [
    "DEFAULT_MAX_RESULTS",
    "MAX_RESULTS",
    "RepositorySearchResult",
    "VectorSearchResult",
    "search_repository",
]
