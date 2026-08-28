from __future__ import annotations

import math
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from repo_dive.errors import InternalOperationError
from repo_dive.indexing.bm25 import build_bm25_index
from repo_dive.indexing.store import IndexStore
from repo_dive.indexing.vectors import (
    ChunkVector,
    EmbeddingIdentity,
    create_chunk_vector,
    pack_float32,
    unpack_float32,
)
from repo_dive.parsing.models import Chunk, ParseResult, create_chunk
from repo_dive.scanner.models import FileRecord, ReadStatus, SourceFile


def identity(*, model: str = "fixtures/minilm") -> EmbeddingIdentity:
    return EmbeddingIdentity(
        provider="sentence-transformers",
        model=model,
        dimensions=3,
    )


def chunks() -> tuple[Chunk, ...]:
    return (
        create_chunk(
            path="src/service.py",
            start_line=1,
            end_line=1,
            text="def alpha(): pass",
        ),
        create_chunk(
            path="src/service.py",
            start_line=2,
            end_line=2,
            text="def beta(): pass",
        ),
    )


def source_file() -> SourceFile:
    text = "def alpha(): pass\ndef beta(): pass\n"
    return SourceFile(
        record=FileRecord(
            path="src/service.py",
            language="python",
            size_bytes=len(text.encode()),
            content_hash="source-hash",
            encoding="utf-8",
            status=ReadStatus.READ,
            skip_reason=None,
        ),
        text=text,
    )


def persist_chunks(store: IndexStore, items: tuple[Chunk, ...]) -> None:
    store.replace_document(source_file(), ParseResult(chunks=items))


def test_float32_codec_has_stable_little_endian_round_trip() -> None:
    encoded = pack_float32((1.0, -2.5, 0.125), dimensions=3)

    assert encoded == b"\x00\x00\x80?\x00\x00 \xc0\x00\x00\x00>"
    assert unpack_float32(encoded, dimensions=3) == (1.0, -2.5, 0.125)


@pytest.mark.parametrize(
    "values",
    [
        (1.0, 2.0),
        (1.0, 2.0, 3.0, 4.0),
        (1.0, math.nan, 3.0),
        (1.0, math.inf, 3.0),
        (1.0, -math.inf, 3.0),
        (1.0, 1e100, 3.0),
    ],
)
def test_float32_codec_rejects_wrong_dimensions_and_non_finite_values(
    values: tuple[float, ...],
) -> None:
    with pytest.raises(ValueError, match="finite float32 values"):
        pack_float32(values, dimensions=3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"provider": "", "model": "model", "dimensions": 3},
        {"provider": "provider", "model": " ", "dimensions": 3},
        {"provider": "provider", "model": "model", "dimensions": 0},
    ],
)
def test_embedding_identity_rejects_incomplete_values(
    kwargs: dict[str, str | int],
) -> None:
    with pytest.raises(ValueError, match="embedding identity"):
        EmbeddingIdentity(**kwargs)  # type: ignore[arg-type]


def test_store_round_trips_float32_vectors_with_identity_and_chunk_hash(
    tmp_path: Path,
) -> None:
    database = tmp_path / "index.sqlite3"
    indexed_chunks = chunks()
    configured = identity()
    vectors = (
        create_chunk_vector(indexed_chunks[0], configured, (1.0, 0.0, 0.25)),
        create_chunk_vector(indexed_chunks[1], configured, (0.0, 1.0, -0.25)),
    )

    with IndexStore.initialize(database) as store:
        persist_chunks(store, indexed_chunks)
        store.replace_vector_index(configured, reversed(vectors))

    with IndexStore.open(database) as store:
        assert store.get_vector_index(configured) == tuple(
            sorted(vectors, key=lambda vector: vector.chunk_id)
        )

    connection = sqlite3.connect(database)
    try:
        assert connection.execute(
            "SELECT chunk_id, provider, model, dimensions, chunk_hash "
            "FROM vectors ORDER BY chunk_id"
        ).fetchall() == [
            (
                vector.chunk_id,
                configured.provider,
                configured.model,
                configured.dimensions,
                vector.chunk_hash,
            )
            for vector in sorted(vectors, key=lambda vector: vector.chunk_id)
        ]
    finally:
        connection.close()


def test_store_rejects_mixed_model_identity_and_preserves_previous_vectors(
    tmp_path: Path,
) -> None:
    database = tmp_path / "index.sqlite3"
    indexed_chunks = chunks()
    configured = identity()
    original = (create_chunk_vector(indexed_chunks[0], configured, (1.0, 0.0, 0.0)),)
    mismatched = (
        original[0],
        create_chunk_vector(
            indexed_chunks[1],
            identity(model="fixtures/other"),
            (0.0, 1.0, 0.0),
        ),
    )

    with IndexStore.initialize(database) as store:
        persist_chunks(store, indexed_chunks)
        store.replace_vector_index(configured, original)

        with pytest.raises(InternalOperationError) as exc_info:
            store.replace_vector_index(configured, mismatched)

        assert exc_info.value.code == "index_vector_identity_mismatch"
        assert store.get_vector_index(configured) == original


def test_store_rejects_stale_chunk_hash_and_duplicate_chunk_id(
    tmp_path: Path,
) -> None:
    database = tmp_path / "index.sqlite3"
    indexed_chunks = chunks()
    configured = identity()
    vector = create_chunk_vector(indexed_chunks[0], configured, (1.0, 0.0, 0.0))

    with IndexStore.initialize(database) as store:
        persist_chunks(store, indexed_chunks)

        with pytest.raises(InternalOperationError) as stale_error:
            store.replace_vector_index(
                configured,
                (replace(vector, chunk_hash="stale-hash"),),
            )
        with pytest.raises(InternalOperationError) as duplicate_error:
            store.replace_vector_index(configured, (vector, vector))

    assert stale_error.value.code == "index_vector_chunk_mismatch"
    assert duplicate_error.value.code == "index_vector_duplicate_chunk"


def test_read_rejects_a_different_model_identity(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    indexed_chunks = chunks()
    configured = identity()

    with IndexStore.initialize(database) as store:
        persist_chunks(store, indexed_chunks)
        store.replace_vector_index(
            configured,
            (create_chunk_vector(indexed_chunks[0], configured, (1.0, 0.0, 0.0)),),
        )

        with pytest.raises(InternalOperationError) as exc_info:
            store.get_vector_index(identity(model="fixtures/other"))

    assert exc_info.value.code == "index_vector_identity_mismatch"


def test_empty_vector_index_does_not_change_bm25_or_chunks(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite3"
    indexed_chunks = chunks()
    bm25 = build_bm25_index(indexed_chunks)

    with IndexStore.initialize(database) as store:
        persist_chunks(store, indexed_chunks)
        store.replace_bm25_index(bm25)

        store.replace_vector_index(identity(), ())

        assert store.get_vector_index(identity()) == ()
        assert store.get_bm25_index() == bm25
        assert store.get_chunks() == indexed_chunks


def test_chunk_vector_constructor_rejects_non_finite_embedding() -> None:
    chunk = chunks()[0]

    with pytest.raises(ValueError, match="finite float32 values"):
        ChunkVector(
            chunk_id=chunk.id,
            chunk_hash=chunk.content_hash,
            identity=identity(),
            embedding=(1.0, math.nan, 0.0),
        )
