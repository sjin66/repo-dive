"""Strict, bounded content contract for one agent-generated Wiki page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from repo_dive.errors import InvocationError
from repo_dive.schema import JsonObject, JsonValue
from repo_dive.wiki.models import Page

PAGE_SUBMISSION_SCHEMA_VERSION = "1.0"
MAX_PAGE_BODY_BYTES = 200_000


@dataclass(frozen=True, slots=True)
class PageSubmission:
    """Caller-owned Markdown and citations, separate from persisted lifecycle state."""

    page_id: str
    body: str
    evidence_ids: tuple[str, ...]
    schema_version: str = PAGE_SUBMISSION_SCHEMA_VERSION


def page_submission_from_document(document: JsonObject) -> PageSubmission:
    """Strictly decode one untrusted page submission document."""
    if set(document) != {"body", "evidence_ids", "page_id", "schema_version"}:
        raise ValueError("Wiki page submission fields are invalid")
    schema_version = _string(document["schema_version"])
    if schema_version != PAGE_SUBMISSION_SCHEMA_VERSION:
        raise ValueError("Wiki page submission Schema is not supported")
    page_id = _string(document["page_id"])
    body = _string(document["body"])
    evidence_ids = _string_tuple(document["evidence_ids"])
    if not page_id or page_id.strip() != page_id:
        raise ValueError("page ID must not be empty or padded")
    if not evidence_ids or any(
        not evidence_id or evidence_id.strip() != evidence_id
        for evidence_id in evidence_ids
    ):
        raise ValueError("Evidence IDs must not be empty or padded")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("Evidence IDs must be unique")
    return PageSubmission(
        page_id=page_id,
        body=body,
        evidence_ids=evidence_ids,
        schema_version=schema_version,
    )


def validate_submission_content(page: Page, submission: PageSubmission) -> None:
    """Validate body limits and citation ownership without disclosing content."""
    if not submission.body.strip() or "\x00" in submission.body:
        raise InvocationError(
            "wiki_page_body_invalid",
            "Wiki page body must be non-empty UTF-8 Markdown without NUL bytes.",
            details={"page_id": page.id},
        )
    try:
        body_bytes = len(submission.body.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise InvocationError(
            "wiki_page_body_invalid",
            "Wiki page body must be valid UTF-8 Markdown.",
            details={"page_id": page.id},
        ) from error
    if body_bytes > MAX_PAGE_BODY_BYTES:
        raise InvocationError(
            "wiki_page_body_too_large",
            "Wiki page body exceeds the supported size.",
            details={"max_bytes": MAX_PAGE_BODY_BYTES, "page_id": page.id},
        )
    known_ids = {reference.evidence_id for reference in page.evidence}
    unknown_count = len(set(submission.evidence_ids) - known_ids)
    if unknown_count:
        raise InvocationError(
            "wiki_page_evidence_unknown",
            "Wiki page submission references unknown Evidence IDs.",
            details={"page_id": page.id, "unknown_count": unknown_count},
        )


def _string(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    return value


def _string_tuple(value: JsonValue) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("value must contain only strings")
    return tuple(cast(list[str], value))


__all__ = [
    "MAX_PAGE_BODY_BYTES",
    "PAGE_SUBMISSION_SCHEMA_VERSION",
    "PageSubmission",
    "page_submission_from_document",
    "validate_submission_content",
]
