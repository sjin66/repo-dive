"""Explainable BM25 retrieval over indexed code Chunks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import log1p

from repo_dive.indexing.bm25 import BM25Index, tokenize_code
from repo_dive.parsing.models import Chunk


@dataclass(frozen=True, slots=True)
class LexicalHit:
    """One BM25-ranked Chunk with its raw score and matched query terms."""

    chunk: Chunk
    lexical_score: float
    matched_terms: tuple[str, ...]


def search_lexical(
    query: str,
    *,
    index: BM25Index,
    chunks: Iterable[Chunk],
    max_results: int = 20,
) -> tuple[LexicalHit, ...]:
    """Return explainable BM25 hits with deterministic tie breaking."""
    if max_results < 0:
        raise ValueError("max_results must not be negative")
    if max_results == 0:
        return ()

    query_terms = tuple(dict.fromkeys(tokenize_code(query)))
    if not query_terms or index.document_count == 0:
        return ()

    chunk_by_id = _chunks_by_id(chunks)
    document_lengths = dict(index.document_lengths)
    document_frequencies = dict(index.document_frequencies)
    relevant_terms = set(query_terms) & document_frequencies.keys()
    if not relevant_terms:
        return ()
    if index.average_document_length <= 0:
        raise ValueError("BM25 average document length must be positive")

    scores: dict[str, float] = {}
    matches: dict[str, set[str]] = {}
    for posting in index.postings:
        if posting.term not in relevant_terms:
            continue
        chunk = chunk_by_id.get(posting.chunk_id)
        document_length = document_lengths.get(posting.chunk_id)
        if chunk is None or document_length is None:
            raise ValueError("BM25 posting references an unavailable Chunk")

        contribution = _term_score(
            term_frequency=posting.term_frequency,
            document_frequency=document_frequencies[posting.term],
            document_length=document_length,
            index=index,
        )
        scores[chunk.id] = scores.get(chunk.id, 0.0) + contribution
        matches.setdefault(chunk.id, set()).add(posting.term)

    hits = [
        LexicalHit(
            chunk=chunk_by_id[chunk_id],
            lexical_score=score,
            matched_terms=tuple(
                term for term in query_terms if term in matches[chunk_id]
            ),
        )
        for chunk_id, score in scores.items()
    ]
    hits.sort(
        key=lambda hit: (
            -hit.lexical_score,
            hit.chunk.path,
            hit.chunk.start_line,
            hit.chunk.id,
        )
    )
    return tuple(hits[:max_results])


def _term_score(
    *,
    term_frequency: int,
    document_frequency: int,
    document_length: int,
    index: BM25Index,
) -> float:
    parameters = index.parameters
    inverse_document_frequency = log1p(
        (index.document_count - document_frequency + 0.5) / (document_frequency + 0.5)
    )
    length_normalization = parameters.k1 * (
        1
        - parameters.b
        + parameters.b * document_length / index.average_document_length
    )
    saturated_term_frequency = (term_frequency * (parameters.k1 + 1)) / (
        term_frequency + length_normalization
    )
    return inverse_document_frequency * saturated_term_frequency


def _chunks_by_id(chunks: Iterable[Chunk]) -> dict[str, Chunk]:
    chunk_by_id: dict[str, Chunk] = {}
    for chunk in chunks:
        if chunk.id in chunk_by_id:
            raise ValueError("lexical corpus contains duplicate Chunk IDs")
        chunk_by_id[chunk.id] = chunk
    return chunk_by_id


__all__ = ["LexicalHit", "search_lexical"]
