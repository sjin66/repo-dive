"""Deterministic brute-force cosine retrieval over persisted embeddings."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import fsum, sqrt

from repo_dive.indexing.vectors import (
    ChunkVector,
    EmbeddingIdentity,
    pack_float32,
    unpack_float32,
)
from repo_dive.parsing.models import Chunk


@dataclass(frozen=True, slots=True)
class VectorHit:
    """One Chunk ranked by its raw cosine similarity score."""

    chunk: Chunk
    vector_score: float


def search_vector(
    query_embedding: Iterable[float],
    *,
    identity: EmbeddingIdentity,
    vectors: Iterable[ChunkVector],
    chunks: Iterable[Chunk],
    max_results: int = 20,
) -> tuple[VectorHit, ...]:
    """Return bounded cosine hits, breaking equal scores by Chunk ID."""
    if max_results < 0:
        raise ValueError("max_results must not be negative")
    if max_results == 0:
        return ()

    try:
        query = unpack_float32(
            pack_float32(query_embedding, dimensions=identity.dimensions),
            dimensions=identity.dimensions,
        )
    except ValueError as error:
        raise ValueError(
            "query embedding must contain finite values with matching dimensions"
        ) from error
    query_norm = _magnitude(query)
    if query_norm == 0.0:
        raise ValueError("query embedding must have non-zero magnitude")

    chunk_by_id = _chunks_by_id(chunks)
    seen_vector_ids: set[str] = set()
    hits: list[VectorHit] = []
    for vector in vectors:
        if vector.chunk_id in seen_vector_ids:
            raise ValueError("vector corpus contains duplicate Chunk IDs")
        seen_vector_ids.add(vector.chunk_id)
        if vector.identity != identity:
            raise ValueError("vector model identity does not match the query")

        chunk = chunk_by_id.get(vector.chunk_id)
        if chunk is None or chunk.content_hash != vector.chunk_hash:
            raise ValueError("vector does not reference a current Chunk")
        embedding = unpack_float32(
            pack_float32(vector.embedding, dimensions=identity.dimensions),
            dimensions=identity.dimensions,
        )
        vector_norm = _magnitude(embedding)
        if vector_norm == 0.0:
            raise ValueError("stored embedding must have non-zero magnitude")
        score = fsum(
            query_value * vector_value
            for query_value, vector_value in zip(query, embedding, strict=True)
        ) / (query_norm * vector_norm)
        hits.append(
            VectorHit(
                chunk=chunk,
                vector_score=max(-1.0, min(1.0, score)),
            )
        )

    hits.sort(key=lambda hit: (-hit.vector_score, hit.chunk.id))
    return tuple(hits[:max_results])


def _magnitude(values: tuple[float, ...]) -> float:
    return sqrt(fsum(value * value for value in values))


def _chunks_by_id(chunks: Iterable[Chunk]) -> dict[str, Chunk]:
    chunk_by_id: dict[str, Chunk] = {}
    for chunk in chunks:
        if chunk.id in chunk_by_id:
            raise ValueError("vector corpus contains duplicate Chunk IDs")
        chunk_by_id[chunk.id] = chunk
    return chunk_by_id


__all__ = ["VectorHit", "search_vector"]
