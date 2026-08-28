"""Shared bounded arguments for repository retrieval commands."""

from __future__ import annotations

import argparse
from typing import cast

from repo_dive.indexing.vectors import EmbeddingIdentity
from repo_dive.providers.embeddings import VectorFailurePolicy
from repo_dive.providers.selection import EmbeddingSelection
from repo_dive.retrieval.service import MAX_RESULTS, VectorSearchResult
from repo_dive.schema import JsonObject

MAX_QUERY_LENGTH = 1_000


def add_embedding_arguments(parser: argparse.ArgumentParser) -> None:
    """Add explicit local-vector configuration shared by RAG commands."""
    parser.add_argument(
        "--embedding-model",
        metavar="DIRECTORY",
        help="existing local Sentence Transformers model directory",
    )
    parser.add_argument(
        "--vector-failure",
        choices=("strict", "degraded"),
        default="strict",
        help="fail or continue without vectors after an explicit vector error",
    )


def vector_failure_policy(value: str) -> VectorFailurePolicy:
    """Narrow one argparse-validated failure policy for typed command code."""
    if value not in ("strict", "degraded"):
        raise ValueError("vector failure policy is invalid")
    return cast(VectorFailurePolicy, value)


def vector_search_document(
    selection: EmbeddingSelection,
    vector: VectorSearchResult | None,
) -> JsonObject:
    """Serialize observable vector state shared by Search and Context."""
    return {
        "error_code": (
            vector.error_code if vector is not None else selection.error_code
        ),
        "failure_policy": selection.failure_policy,
        "identity": _identity_document(
            vector.identity if vector is not None else selection.identity
        ),
        "indexed_chunks": vector.indexed_chunks if vector is not None else 0,
        "query_embeddings": vector.query_embeddings if vector is not None else 0,
        "status": vector.status if vector is not None else "degraded",
    }


def vector_warning(vector: VectorSearchResult | None) -> str | None:
    """Return one safe warning for a degraded vector query."""
    if vector is None or vector.error_code is None:
        return None
    return f"vector_degraded:{vector.error_code}"


def _identity_document(identity: EmbeddingIdentity | None) -> JsonObject | None:
    if identity is None:
        return None
    return {
        "dimensions": identity.dimensions,
        "model": identity.model,
        "provider": identity.provider,
    }


def query_value(value: str) -> str:
    """Validate and normalize an externally supplied retrieval query."""
    query = value.strip()
    if not query:
        raise argparse.ArgumentTypeError("query must not be empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise argparse.ArgumentTypeError(
            f"query must not exceed {MAX_QUERY_LENGTH} characters"
        )
    return query


def result_limit(value: str) -> int:
    """Parse a bounded positive retrieval result count."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be an integer") from error
    if not 1 <= parsed <= MAX_RESULTS:
        raise argparse.ArgumentTypeError(f"value must be from 1 to {MAX_RESULTS}")
    return parsed


def positive_token_budget(value: str) -> int:
    """Parse a positive token budget shared by Context and Wiki commands."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


__all__ = [
    "MAX_QUERY_LENGTH",
    "add_embedding_arguments",
    "positive_token_budget",
    "query_value",
    "result_limit",
    "vector_failure_policy",
    "vector_search_document",
    "vector_warning",
]
