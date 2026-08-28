"""Pure deterministic assembly of persisted Wiki state into Markdown."""

from __future__ import annotations

import hashlib
from typing import Literal
from urllib.parse import quote

from repo_dive.wiki.models import EvidenceRef, Page, PageStatus, Wiki

AnchorKind = Literal["page", "section"]


def stable_anchor(kind: AnchorKind, identifier: str) -> str:
    """Return an ASCII-only anchor stable for one typed persisted identifier."""
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"{kind}-{digest}"


def assemble_wiki(wiki: Wiki) -> str:
    """Assemble one complete Wiki without timestamps or filesystem access."""
    pages = tuple(page for section in wiki.sections for page in section.pages)
    _validate_generated_pages(pages)
    page_by_id = {page.id: page for page in pages}
    lines = [
        f"# {_heading_text(wiki.title)}",
        "",
        wiki.description.rstrip("\r\n"),
        "",
        "## Contents",
        "",
    ]
    for section in wiki.sections:
        section_anchor = stable_anchor("section", section.id)
        lines.append(f"- [{_link_text(section.title)}](#{section_anchor})")
        lines.extend(
            f"  - [{_link_text(page.title)}](#{stable_anchor('page', page.id)})"
            for page in section.pages
        )
    lines.append("")

    for section in wiki.sections:
        section_anchor = stable_anchor("section", section.id)
        lines.extend(
            (
                f'<a id="{section_anchor}"></a>',
                f"## {_heading_text(section.title)}",
                "",
            )
        )
        for page in section.pages:
            lines.extend(_page_markdown(page, page_by_id))
    return "\n".join(lines).rstrip("\n") + "\n"


def _validate_generated_pages(pages: tuple[Page, ...]) -> None:
    for page in pages:
        if (
            page.status is not PageStatus.GENERATED
            or page.body is None
            or not page.citation_ids
        ):
            raise ValueError("generated page content is incomplete")


def _page_markdown(page: Page, page_by_id: dict[str, Page]) -> tuple[str, ...]:
    if page.body is None:  # pragma: no cover - validated before assembly
        raise ValueError("generated page content is incomplete")
    references = {reference.evidence_id: reference for reference in page.evidence}
    lines = [
        f'<a id="{stable_anchor("page", page.id)}"></a>',
        f"### {_heading_text(page.title)}",
        "",
        page.body.rstrip("\r\n"),
        "",
    ]
    if page.related_page_ids:
        lines.extend(("#### Related pages", ""))
        lines.extend(
            f"- [{_link_text(page_by_id[related_id].title)}]"
            f"(#{stable_anchor('page', related_id)})"
            for related_id in page.related_page_ids
        )
        lines.append("")
    lines.extend(("#### Sources", ""))
    lines.extend(_source_link(references[citation]) for citation in page.citation_ids)
    lines.append("")
    return tuple(lines)


def _source_link(reference: EvidenceRef) -> str:
    if reference.start_line == reference.end_line:
        label_lines = str(reference.start_line)
        fragment = f"#L{reference.start_line}"
    else:
        label_lines = f"{reference.start_line}-{reference.end_line}"
        fragment = f"#L{reference.start_line}-L{reference.end_line}"
    label = _link_text(f"{reference.path}:{label_lines}")
    target = f"../{quote(reference.path, safe='/')}{fragment}"
    return f"- [{label}]({target})"


def _heading_text(value: str) -> str:
    return " ".join(value.splitlines())


def _link_text(value: str) -> str:
    return (
        _heading_text(value)
        .replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


__all__ = ["assemble_wiki", "stable_anchor"]
