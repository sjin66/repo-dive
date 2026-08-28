"""Shared bounded arguments for repository retrieval commands."""

from __future__ import annotations

import argparse

from repo_dive.retrieval.service import MAX_RESULTS

MAX_QUERY_LENGTH = 1_000


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
    "positive_token_budget",
    "query_value",
    "result_limit",
]
