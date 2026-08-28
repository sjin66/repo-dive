from __future__ import annotations

import math
from dataclasses import replace

import pytest

from repo_dive.indexing.vectors import EmbeddingIdentity, create_chunk_vector
from repo_dive.parsing.models import Chunk, create_chunk
from repo_dive.retrieval.vector import search_vector


def identity(
    *, dimensions: int = 2, model: str = "fixtures/minilm"
) -> EmbeddingIdentity:
    return EmbeddingIdentity(
        provider="sentence-transformers",
        model=model,
        dimensions=dimensions,
    )


def make_chunk(path: str, line: int, text: str) -> Chunk:
    return create_chunk(
        path=path,
        start_line=line,
        end_line=line,
        text=text,
    )


def test_cosine_scores_and_ranking_match_fixed_manual_result() -> None:
    chunks = (
        make_chunk("opposite.py", 1, "opposite"),
        make_chunk("diagonal.py", 1, "diagonal"),
        make_chunk("exact.py", 1, "exact"),
    )
    configured = identity()
    vectors = (
        create_chunk_vector(chunks[0], configured, (-1.0, 0.0)),
        create_chunk_vector(chunks[1], configured, (1.0, 1.0)),
        create_chunk_vector(chunks[2], configured, (2.0, 0.0)),
    )

    hits = search_vector(
        (1.0, 0.0),
        identity=configured,
        vectors=reversed(vectors),
        chunks=reversed(chunks),
        max_results=3,
    )

    assert [hit.chunk.path for hit in hits] == [
        "exact.py",
        "diagonal.py",
        "opposite.py",
    ]
    assert [hit.vector_score for hit in hits] == pytest.approx(
        [1.0, 1.0 / math.sqrt(2.0), -1.0]
    )


def test_equal_scores_use_chunk_id_as_stable_tie_breaker() -> None:
    chunks = (
        make_chunk("z.py", 1, "first"),
        make_chunk("a.py", 1, "second"),
        make_chunk("m.py", 1, "third"),
    )
    configured = identity()
    vectors = tuple(
        create_chunk_vector(chunk, configured, (1.0, 1.0)) for chunk in chunks
    )

    hits = search_vector(
        (1.0, 1.0),
        identity=configured,
        vectors=reversed(vectors),
        chunks=chunks,
    )

    assert [hit.chunk.id for hit in hits] == sorted(chunk.id for chunk in chunks)


def test_max_results_bounds_output_and_zero_skips_work() -> None:
    chunks = tuple(make_chunk(f"{index}.py", 1, str(index)) for index in range(5))
    configured = identity()
    vectors = tuple(
        create_chunk_vector(chunk, configured, (float(index + 1), 1.0))
        for index, chunk in enumerate(chunks)
    )

    hits = search_vector(
        (1.0, 0.0),
        identity=configured,
        vectors=vectors,
        chunks=chunks,
        max_results=2,
    )

    assert len(hits) == 2
    assert (
        search_vector(
            (1.0, 0.0),
            identity=configured,
            vectors=vectors,
            chunks=chunks,
            max_results=0,
        )
        == ()
    )


def test_empty_vector_collection_returns_no_hits() -> None:
    assert (
        search_vector(
            (1.0, 0.0),
            identity=identity(),
            vectors=(),
            chunks=(),
        )
        == ()
    )


@pytest.mark.parametrize(
    "query",
    [
        (1.0,),
        (1.0, 0.0, 0.0),
        (math.nan, 0.0),
        (math.inf, 0.0),
        (0.0, 0.0),
    ],
)
def test_invalid_query_embedding_is_rejected(query: tuple[float, ...]) -> None:
    with pytest.raises(ValueError, match="query embedding"):
        search_vector(
            query,
            identity=identity(),
            vectors=(),
            chunks=(),
        )


def test_negative_max_results_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_results must not be negative"):
        search_vector(
            (1.0, 0.0),
            identity=identity(),
            vectors=(),
            chunks=(),
            max_results=-1,
        )


def test_model_identity_mismatch_is_rejected() -> None:
    chunk = make_chunk("a.py", 1, "alpha")
    configured = identity()
    vector = create_chunk_vector(chunk, configured, (1.0, 0.0))

    with pytest.raises(ValueError, match="model identity"):
        search_vector(
            (1.0, 0.0),
            identity=identity(model="fixtures/other"),
            vectors=(vector,),
            chunks=(chunk,),
        )


def test_stale_or_missing_chunk_is_rejected() -> None:
    chunk = make_chunk("a.py", 1, "alpha")
    configured = identity()
    vector = create_chunk_vector(chunk, configured, (1.0, 0.0))

    with pytest.raises(ValueError, match="current Chunk"):
        search_vector(
            (1.0, 0.0),
            identity=configured,
            vectors=(replace(vector, chunk_hash="stale"),),
            chunks=(chunk,),
        )
    with pytest.raises(ValueError, match="current Chunk"):
        search_vector(
            (1.0, 0.0),
            identity=configured,
            vectors=(vector,),
            chunks=(),
        )
