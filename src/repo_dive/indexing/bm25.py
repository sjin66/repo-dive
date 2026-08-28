"""Deterministic code-aware tokenization and BM25 corpus construction."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from repo_dive.parsing.models import Chunk

TOKENIZER_VERSION = "code-v1"
DEFAULT_K1 = 1.2
DEFAULT_B = 0.75

_CODE_TOKEN = re.compile(r"\w+(?:(?:::|[./:\\-])\w+)*", flags=re.UNICODE)
_CODE_SEPARATOR = re.compile(r"[_./:\\-]+")
_ACRONYM_BOUNDARY = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


@dataclass(frozen=True, slots=True)
class BM25Parameters:
    """Versioned constants required to reproduce BM25 scoring."""

    k1: float = DEFAULT_K1
    b: float = DEFAULT_B
    tokenizer_version: str = TOKENIZER_VERSION

    def __post_init__(self) -> None:
        if self.k1 <= 0:
            raise ValueError("BM25 k1 must be positive")
        if not 0 <= self.b <= 1:
            raise ValueError("BM25 b must be between 0 and 1")
        if not self.tokenizer_version:
            raise ValueError("BM25 tokenizer version must not be empty")


@dataclass(frozen=True, slots=True)
class Posting:
    """One term occurrence summary for one indexed Chunk."""

    term: str
    chunk_id: str
    term_frequency: int


@dataclass(frozen=True, slots=True)
class BM25Index:
    """Complete deterministic lexical corpus data ready for persistence."""

    parameters: BM25Parameters
    document_count: int
    total_document_length: int
    average_document_length: float
    document_lengths: tuple[tuple[str, int], ...]
    document_frequencies: tuple[tuple[str, int], ...]
    postings: tuple[Posting, ...]


def tokenize_code(text: str) -> tuple[str, ...]:
    """Return whole code tokens plus case-folded and structural parts."""
    tokens: list[str] = []
    for match in _CODE_TOKEN.finditer(text):
        whole = match.group(0)
        variants: list[str] = []
        seen: set[str] = set()

        _append_variant(variants, seen, whole)
        _append_variant(variants, seen, whole.casefold())
        for segment in _CODE_SEPARATOR.split(whole):
            if not segment:
                continue
            for part in _split_camel_case(segment):
                _append_variant(variants, seen, part)
                _append_variant(variants, seen, part.casefold())

        tokens.extend(variants)
    return tuple(tokens)


def build_bm25_index(
    chunks: Iterable[Chunk],
    *,
    parameters: BM25Parameters | None = None,
) -> BM25Index:
    """Build stable postings and corpus statistics from parsed Chunks."""
    configured = parameters or BM25Parameters()
    ordered_chunks = sorted(chunks, key=lambda chunk: chunk.id)
    chunk_ids = [chunk.id for chunk in ordered_chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("BM25 corpus contains duplicate Chunk IDs")

    document_lengths: list[tuple[str, int]] = []
    document_frequencies: Counter[str] = Counter()
    postings: list[Posting] = []

    for chunk in ordered_chunks:
        frequencies = Counter(tokenize_code(chunk.text))
        document_lengths.append((chunk.id, sum(frequencies.values())))
        document_frequencies.update(frequencies.keys())
        postings.extend(
            Posting(
                term=term,
                chunk_id=chunk.id,
                term_frequency=term_frequency,
            )
            for term, term_frequency in sorted(frequencies.items())
        )

    postings.sort(key=lambda posting: (posting.term, posting.chunk_id))
    total_document_length = sum(length for _, length in document_lengths)
    document_count = len(document_lengths)
    average_document_length = (
        total_document_length / document_count if document_count else 0.0
    )
    return BM25Index(
        parameters=configured,
        document_count=document_count,
        total_document_length=total_document_length,
        average_document_length=average_document_length,
        document_lengths=tuple(document_lengths),
        document_frequencies=tuple(sorted(document_frequencies.items())),
        postings=tuple(postings),
    )


def _append_variant(values: list[str], seen: set[str], value: str) -> None:
    if value and value not in seen:
        values.append(value)
        seen.add(value)


def _split_camel_case(value: str) -> tuple[str, ...]:
    with_acronyms = _ACRONYM_BOUNDARY.sub(r"\1 \2", value)
    separated = _CAMEL_BOUNDARY.sub(r"\1 \2", with_acronyms)
    return tuple(separated.split())


__all__ = [
    "BM25Index",
    "BM25Parameters",
    "DEFAULT_B",
    "DEFAULT_K1",
    "Posting",
    "TOKENIZER_VERSION",
    "build_bm25_index",
    "tokenize_code",
]
