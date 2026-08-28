"""Typed float32 embeddings bound to indexed Chunk identities."""

from __future__ import annotations

import struct
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

from repo_dive.parsing.models import Chunk


@dataclass(frozen=True, slots=True)
class EmbeddingIdentity:
    """The provider, model, and dimensions that define an embedding space."""

    provider: str
    model: str
    dimensions: int

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model.strip() or self.dimensions <= 0:
            raise ValueError(
                "embedding identity requires provider, model, and positive dimensions"
            )


@dataclass(frozen=True, slots=True)
class ChunkVector:
    """One validated embedding tied to the exact content of one Chunk."""

    chunk_id: str
    chunk_hash: str
    identity: EmbeddingIdentity
    embedding: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.chunk_id or not self.chunk_hash:
            raise ValueError("Chunk vector requires a Chunk ID and content hash")
        pack_float32(self.embedding, dimensions=self.identity.dimensions)


def create_chunk_vector(
    chunk: Chunk,
    identity: EmbeddingIdentity,
    embedding: Iterable[float],
) -> ChunkVector:
    """Create a Chunk-bound vector normalized to persisted float32 precision."""
    encoded = pack_float32(embedding, dimensions=identity.dimensions)
    return ChunkVector(
        chunk_id=chunk.id,
        chunk_hash=chunk.content_hash,
        identity=identity,
        embedding=unpack_float32(encoded, dimensions=identity.dimensions),
    )


def pack_float32(values: Iterable[float], *, dimensions: int) -> bytes:
    """Encode exactly ``dimensions`` finite values as little-endian float32."""
    if dimensions <= 0:
        raise ValueError("embedding must contain exactly finite float32 values")
    try:
        normalized = tuple(float(value) for value in values)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            "embedding must contain exactly finite float32 values"
        ) from error
    if len(normalized) != dimensions or any(
        not isfinite(value) for value in normalized
    ):
        raise ValueError("embedding must contain exactly finite float32 values")
    try:
        encoded = struct.pack(f"<{dimensions}f", *normalized)
    except (OverflowError, struct.error) as error:
        raise ValueError(
            "embedding must contain exactly finite float32 values"
        ) from error
    if any(not isfinite(value) for value in struct.unpack(f"<{dimensions}f", encoded)):
        raise ValueError("embedding must contain exactly finite float32 values")
    return encoded


def unpack_float32(value: bytes, *, dimensions: int) -> tuple[float, ...]:
    """Decode and validate one little-endian float32 embedding."""
    if dimensions <= 0 or len(value) != dimensions * 4:
        raise ValueError("embedding must contain exactly finite float32 values")
    try:
        decoded = struct.unpack(f"<{dimensions}f", value)
    except struct.error as error:
        raise ValueError(
            "embedding must contain exactly finite float32 values"
        ) from error
    if any(not isfinite(item) for item in decoded):
        raise ValueError("embedding must contain exactly finite float32 values")
    return decoded


__all__ = [
    "ChunkVector",
    "EmbeddingIdentity",
    "create_chunk_vector",
    "pack_float32",
    "unpack_float32",
]
