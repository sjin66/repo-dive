from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

import pytest

from repo_dive.indexing.bm25 import build_bm25_index
from repo_dive.parsing.models import Chunk, create_chunk
from repo_dive.retrieval.lexical import search_lexical


def make_chunks(specs: Iterable[tuple[str, int, str]]) -> tuple[Chunk, ...]:
    return tuple(
        create_chunk(
            path=path,
            start_line=start_line,
            end_line=start_line,
            text=text,
        )
        for path, start_line, text in specs
    )


def test_scores_fixed_corpus_with_standard_bm25_formula() -> None:
    chunks = make_chunks(
        (
            ("a.py", 1, "alpha alpha beta"),
            ("b.py", 1, "alpha beta beta beta"),
            ("c.py", 1, "gamma"),
        )
    )

    hits = search_lexical(
        "alpha",
        index=build_bm25_index(chunks),
        chunks=chunks,
        max_results=10,
    )

    assert [hit.chunk.path for hit in hits] == ["a.py", "b.py"]
    assert hits[0].lexical_score == pytest.approx(0.6243067075264112)
    assert hits[1].lexical_score == pytest.approx(0.39019169220400696)
    assert [hit.matched_terms for hit in hits] == [("alpha",), ("alpha",)]


def test_sums_unique_query_terms_and_explains_each_match() -> None:
    chunks = make_chunks(
        (
            ("a.py", 1, "alpha beta"),
            ("b.py", 1, "alpha"),
        )
    )
    index = build_bm25_index(chunks)

    once = search_lexical("alpha beta", index=index, chunks=chunks)
    repeated = search_lexical("alpha alpha beta", index=index, chunks=chunks)

    assert repeated == once
    assert once[0].matched_terms == ("alpha", "beta")
    assert once[1].matched_terms == ("alpha",)
    assert once[0].lexical_score > once[1].lexical_score


def test_equal_scores_use_path_line_and_chunk_id_as_stable_tie_breakers() -> None:
    generated = make_chunks(
        (
            ("b.py", 1, "needle"),
            ("a.py", 9, "needle"),
            ("a.py", 3, "needle"),
            ("a.py", 3, "needle"),
        )
    )
    chunks = (*generated[:3], replace(generated[3], id=f"{generated[3].id}:tie"))

    hits = search_lexical(
        "needle",
        index=build_bm25_index(chunks),
        chunks=reversed(chunks),
    )

    assert [
        (hit.chunk.path, hit.chunk.start_line, hit.chunk.id) for hit in hits
    ] == sorted((chunk.path, chunk.start_line, chunk.id) for chunk in chunks)


@pytest.mark.parametrize("query", ["", "   ", "{} ->"])
def test_empty_or_tokenless_query_returns_no_hits(query: str) -> None:
    chunks = make_chunks((("a.py", 1, "alpha"),))

    assert search_lexical(query, index=build_bm25_index(chunks), chunks=chunks) == ()


def test_unknown_terms_and_zero_max_results_return_no_hits() -> None:
    chunks = make_chunks((("a.py", 1, "alpha"),))
    index = build_bm25_index(chunks)

    assert search_lexical("unknown", index=index, chunks=chunks) == ()
    assert search_lexical("alpha", index=index, chunks=chunks, max_results=0) == ()


def test_negative_max_results_is_rejected() -> None:
    chunks = make_chunks((("a.py", 1, "alpha"),))

    with pytest.raises(ValueError, match="max_results must not be negative"):
        search_lexical(
            "alpha",
            index=build_bm25_index(chunks),
            chunks=chunks,
            max_results=-1,
        )
