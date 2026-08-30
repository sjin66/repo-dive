"""Strict, bounded content contract for one agent-generated Wiki page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from markdown_it import MarkdownIt

from repo_dive.errors import InvocationError
from repo_dive.schema import JsonObject, JsonValue
from repo_dive.wiki.models import Page, SubsectionContent

PAGE_SUBMISSION_SCHEMA_VERSION = "2.0"
MAX_PAGE_BODY_BYTES = 200_000


@dataclass(frozen=True, slots=True)
class PageSubmission:
    """Caller-owned Markdown and citations, separate from persisted lifecycle state."""

    page_id: str
    subsections: tuple[SubsectionContent, ...]
    schema_version: str = PAGE_SUBMISSION_SCHEMA_VERSION


def page_submission_from_document(document: JsonObject) -> PageSubmission:
    """Strictly decode one untrusted page submission document."""
    if set(document) != {"page_id", "schema_version", "subsections"}:
        raise ValueError("Wiki page submission fields are invalid")
    schema_version = _string(document["schema_version"])
    if schema_version != PAGE_SUBMISSION_SCHEMA_VERSION:
        raise ValueError("Wiki page submission Schema is not supported")
    page_id = _string(document["page_id"])
    subsection_values = document["subsections"]
    if not isinstance(subsection_values, list):
        raise TypeError("subsections must be an array")
    subsections = tuple(
        _subsection_content(_object(value)) for value in subsection_values
    )
    if not page_id or page_id.strip() != page_id:
        raise ValueError("page ID must not be empty or padded")
    if not subsections:
        raise ValueError("Page submission Subsections must not be empty")
    return PageSubmission(
        page_id=page_id,
        subsections=subsections,
        schema_version=schema_version,
    )


def validate_submission_content(page: Page, submission: PageSubmission) -> None:
    """Validate body limits and citation ownership without disclosing content."""
    expected_ids = tuple(item.id for item in page.subsections)
    actual_ids = tuple(item.subsection_id for item in submission.subsections)
    if actual_ids != expected_ids:
        raise InvocationError(
            "wiki_page_subsections_invalid",
            "Wiki page submission must contain every Subsection in contract order.",
            details={"page_id": page.id},
        )
    try:
        body_bytes = sum(
            len(item.body.encode("utf-8")) for item in submission.subsections
        )
    except UnicodeEncodeError as error:
        raise InvocationError(
            "wiki_page_body_invalid",
            "Wiki Subsection bodies must be valid UTF-8 Markdown.",
            details={"page_id": page.id},
        ) from error
    if body_bytes > MAX_PAGE_BODY_BYTES:
        raise InvocationError(
            "wiki_page_body_too_large",
            "Wiki page body exceeds the supported size.",
            details={"max_bytes": MAX_PAGE_BODY_BYTES, "page_id": page.id},
        )
    for content in submission.subsections:
        _validate_fragment(page.id, content)
    known_ids = {reference.evidence_id for reference in page.evidence}
    submitted_ids = {
        evidence_id
        for content in submission.subsections
        for evidence_id in content.evidence_ids
    }
    unknown_count = len(submitted_ids - known_ids)
    if unknown_count:
        raise InvocationError(
            "wiki_page_evidence_unknown",
            "Wiki page submission references unknown Evidence IDs.",
            details={"page_id": page.id, "unknown_count": unknown_count},
        )
    references = {reference.evidence_id: reference for reference in page.evidence}
    for contract, content in zip(page.subsections, submission.subsections, strict=True):
        if contract.documentation_only:
            continue
        if not any(
            references[evidence_id].role == "direct"
            and contract.id in references[evidence_id].subsection_ids
            for evidence_id in content.evidence_ids
        ):
            raise InvocationError(
                "wiki_page_direct_evidence_missing",
                "Wiki Subsection must cite required direct Evidence.",
                details={"page_id": page.id, "subsection_id": contract.id},
            )


def _validate_fragment(page_id: str, content: SubsectionContent) -> None:
    if "\x00" in content.body:
        raise InvocationError(
            "wiki_page_body_invalid",
            "Wiki Subsection bodies must not contain NUL bytes.",
            details={"page_id": page_id, "subsection_id": content.subsection_id},
        )
    parser = MarkdownIt("commonmark", {"html": True})
    for token in parser.parse(content.body):
        if token.type == "heading_open" and token.tag in {"h1", "h2", "h3", "h4"}:
            line = (token.map[0] + 1) if token.map is not None else 1
            raise InvocationError(
                "wiki_page_heading_level_invalid",
                "Caller Markdown headings must use only H5 or H6.",
                details={
                    "line": line,
                    "page_id": page_id,
                    "subsection_id": content.subsection_id,
                },
            )
        if token.type in {"html_block", "html_inline"}:
            line = (token.map[0] + 1) if token.map is not None else 1
            raise InvocationError(
                "wiki_page_html_invalid",
                "Caller Markdown must not contain raw HTML.",
                details={
                    "line": line,
                    "page_id": page_id,
                    "subsection_id": content.subsection_id,
                },
            )


def _object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("value must be an object")
    return value


def _subsection_content(document: JsonObject) -> SubsectionContent:
    if set(document) != {"body", "evidence_ids", "subsection_id"}:
        raise ValueError("Wiki Subsection submission fields are invalid")
    return SubsectionContent(
        subsection_id=_string(document["subsection_id"]),
        body=_string(document["body"]),
        evidence_ids=_string_tuple(document["evidence_ids"]),
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
