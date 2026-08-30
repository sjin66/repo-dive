"""Pure deterministic assembly of governed Wiki state into Markdown."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

from repo_dive.wiki.models import EvidenceRef, Page, PageStatus, Wiki

AnchorKind = Literal["page", "section"]


@dataclass(frozen=True, slots=True)
class WikiBuildContext:
    """Exact index and source identity disclosed by one Wiki publication."""

    scan_mode: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    effective_default_excluded_directories: tuple[str, ...]
    indexed_files: int
    skipped_files: int
    index_build_id: str
    repository_fingerprint: str
    source_control: str
    source_commit: str | None
    source_dirty: bool | None
    generated_at: str


def stable_anchor(kind: AnchorKind, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"{kind}-{digest}"


def subsection_anchor(page_id: str, subsection_id: str) -> str:
    digest = hashlib.sha256(f"{page_id}\0{subsection_id}".encode()).hexdigest()
    return f"subsection-{digest}"


def assemble_wiki(wiki: Wiki, context: WikiBuildContext | None = None) -> str:
    """Assemble one complete Wiki from validated state and immutable build context."""
    pages = tuple(page for section in wiki.sections for page in section.pages)
    _validate_generated_pages(pages)
    page_by_id = {page.id: page for page in pages}
    labels = dict(wiki.framework_labels)
    if context is not None:
        _require_framework_labels(labels)
    contents = (
        labels["contents"]
        if context is not None
        else labels.get("contents", "Contents")
    )
    lines = [f"# {_heading_text(wiki.title)}", "", wiki.description.rstrip("\r\n"), ""]
    if context is not None:
        lines.extend(_scope_markdown(labels, context))
    lines.extend((f"## {_heading_text(contents)}", ""))
    for section in wiki.sections:
        section_anchor = stable_anchor("section", section.id)
        lines.append(f"- [{_link_text(section.title)}](#{section_anchor})")
        for page in section.pages:
            lines.append(
                f"  - [{_link_text(page.title)}](#{stable_anchor('page', page.id)})"
            )
            lines.extend(
                f"    - [{_link_text(subsection.title)}]"
                f"(#{subsection_anchor(page.id, subsection.id)})"
                for subsection in page.subsections
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
            lines.extend(
                _page_markdown(page, page_by_id, labels, governed=context is not None)
            )
    return "\n".join(lines).rstrip("\n") + "\n"


def _scope_markdown(
    labels: dict[str, str], context: WikiBuildContext
) -> tuple[str, ...]:
    def value(key: str, _fallback: str) -> str:
        return labels[key]

    commit = context.source_commit or value("source_commit_none", "none")
    dirty = (
        value("source_state_non_git", "non-Git")
        if context.source_control == "non_git"
        else value("source_state_dirty", "dirty")
        if context.source_dirty
        else value("source_state_clean", "clean")
    )
    include = ", ".join(context.include) or value("patterns_none", "none")
    exclude = ", ".join(context.exclude) or value("patterns_none", "none")
    defaults = ", ".join(context.effective_default_excluded_directories)
    scope_lines = [
        f"**{_heading_text(value('scope_version', 'Scope and version'))}**",
        "",
        f"- {value('scan_mode', 'Scan mode')}: `{context.scan_mode}`",
    ]
    if context.scan_mode == "git":
        git_scope_description = value(
            "git_scope_description",
            "tracked plus unignored untracked files after the recorded filters",
        )
        scope_lines.append(
            f"- {value('git_scope', 'Git corpus')}: {git_scope_description}"
        )
    scope_lines.extend(
        (
            f"- {value('include_patterns', 'Include patterns')}: `{include}`",
            f"- {value('exclude_patterns', 'Exclude patterns')}: `{exclude}`",
            f"- {value('default_exclusions', 'Default excluded directories')}: "
            f"`{defaults}`",
            f"- {value('indexed_files', 'Indexed files')}: {context.indexed_files}",
            f"- {value('skipped_files', 'Skipped files')}: {context.skipped_files}",
            f"- {value('index_build', 'Index build')}: `{context.index_build_id}`",
            f"- {value('repository_fingerprint', 'Repository fingerprint')}: "
            f"`{context.repository_fingerprint}`",
            f"- {value('source_commit', 'Source commit')}: `{commit}`",
            f"- {value('source_state', 'Source state')}: `{dirty}`",
            f"- {value('generated_at', 'Generated at')}: `{context.generated_at}`",
            "",
        )
    )
    return tuple(scope_lines)


def _validate_generated_pages(pages: tuple[Page, ...]) -> None:
    for page in pages:
        if (
            page.status is not PageStatus.GENERATED
            or (not page.subsection_contents and page.body is None)
            or not page.citation_ids
        ):
            raise ValueError("generated page content is incomplete")


def _page_markdown(
    page: Page,
    page_by_id: dict[str, Page],
    labels: dict[str, str],
    *,
    governed: bool,
) -> tuple[str, ...]:
    references = {reference.evidence_id: reference for reference in page.evidence}
    lines = [
        f'<a id="{stable_anchor("page", page.id)}"></a>',
        f"### {_heading_text(page.title)}",
        "",
    ]
    for contract, content in zip(
        page.subsections, page.subsection_contents, strict=True
    ):
        lines.extend(
            (
                f'<a id="{subsection_anchor(page.id, contract.id)}"></a>',
                f"#### {_heading_text(contract.title)}",
                "",
                content.body.rstrip("\r\n"),
                "",
            )
        )
    if page.related_page_ids:
        related_label = (
            labels["related_pages"]
            if governed
            else labels.get("related_pages", "Related pages")
        )
        lines.extend((f"#### {_heading_text(related_label)}", ""))
        lines.extend(
            f"- [{_link_text(page_by_id[related_id].title)}]"
            f"(#{stable_anchor('page', related_id)})"
            for related_id in page.related_page_ids
        )
        lines.append("")
    sources_label = labels["sources"] if governed else labels.get("sources", "Sources")
    lines.extend((f"#### {_heading_text(sources_label)}", ""))
    lines.extend(_source_link(references[citation]) for citation in page.citation_ids)
    lines.append("")
    return tuple(lines)


def _require_framework_labels(labels: dict[str, str]) -> None:
    required = {
        "contents",
        "related_pages",
        "sources",
        "scope_version",
        "scan_mode",
        "git_scope",
        "git_scope_description",
        "include_patterns",
        "exclude_patterns",
        "default_exclusions",
        "indexed_files",
        "skipped_files",
        "index_build",
        "repository_fingerprint",
        "source_commit",
        "source_state",
        "source_state_clean",
        "source_state_dirty",
        "source_state_non_git",
        "source_commit_none",
        "patterns_none",
        "generated_at",
    }
    if set(labels) != required:
        raise ValueError("governed Wiki framework labels are incomplete or unexpected")


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


__all__ = ["WikiBuildContext", "assemble_wiki", "stable_anchor", "subsection_anchor"]
