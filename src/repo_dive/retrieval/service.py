"""Read-only orchestration over one validated published repository index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repo_dive.errors import RepositoryError
from repo_dive.indexing.graph import SymbolGraph
from repo_dive.indexing.service import load_published_index
from repo_dive.indexing.store import IndexStore
from repo_dive.parsing.models import Symbol
from repo_dive.retrieval.fusion import FusionResult, fuse_hits
from repo_dive.retrieval.lexical import search_lexical
from repo_dive.retrieval.structural import search_structural

DEFAULT_MAX_RESULTS = 10
MAX_RESULTS = 50
CANDIDATE_MULTIPLIER = 4
MAX_CANDIDATES = MAX_RESULTS * CANDIDATE_MULTIPLIER


@dataclass(frozen=True, slots=True)
class RepositorySearchResult:
    """A reproducible fused result plus source symbols needed for formatting."""

    repository: Path
    build_id: str
    fusion: FusionResult
    symbols: tuple[Symbol, ...]


def search_repository(
    repository: str | Path,
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> RepositorySearchResult:
    """Search a current index without mutating repository-owned artifacts."""
    if not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"max_results must be from 1 to {MAX_RESULTS}")

    published = load_published_index(repository)
    candidate_limit = min(max_results * CANDIDATE_MULTIPLIER, MAX_CANDIDATES)
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
        fusion = fuse_hits(
            lexical_hits=lexical_hits,
            structural_hits=structural_hits,
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
    )


__all__ = [
    "DEFAULT_MAX_RESULTS",
    "MAX_RESULTS",
    "RepositorySearchResult",
    "search_repository",
]
