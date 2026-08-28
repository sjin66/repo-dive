"""Freshness validation for persisted page Evidence against the current index."""

from __future__ import annotations

from pathlib import Path

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import PublishedIndex, load_published_index
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION, IndexStore
from repo_dive.parsing.models import Chunk
from repo_dive.wiki.models import Page, PageStatus, Wiki


def stale_page_ids(repository: str | Path, wiki: Wiki) -> tuple[str, ...]:
    """Return Page IDs whose saved Evidence cannot be trusted by consumers."""
    return stale_page_ids_for_index(load_published_index(repository), wiki)


def stale_page_ids_for_index(
    published: PublishedIndex,
    wiki: Wiki,
) -> tuple[str, ...]:
    """Return stale Page IDs using one already validated published index."""
    chunks = _chunks_by_id(published)
    return tuple(
        page.id
        for section in wiki.sections
        for page in section.pages
        if _page_is_stale(page, chunks)
    )


def validate_page_evidence(repository: str | Path, page: Page) -> None:
    """Reject missing or stale Evidence before page submission or Wiki build."""
    if not page.evidence or page.evidence_snapshot is None:
        raise RepositoryError(
            "wiki_evidence_missing",
            "Wiki page does not have a complete Evidence snapshot.",
            details={"page_id": page.id},
        )
    published = load_published_index(repository)
    if _page_is_stale(page, _chunks_by_id(published)):
        raise RepositoryError(
            "wiki_evidence_stale",
            "Wiki page Evidence is stale for the current repository index.",
            details={"page_id": page.id},
        )


def _chunks_by_id(published: PublishedIndex) -> dict[str, Chunk]:
    with IndexStore.open_readonly(published.database) as store:
        return {chunk.id: chunk for chunk in store.get_chunks()}


def _page_is_stale(page: Page, chunks: dict[str, Chunk]) -> bool:
    snapshot = page.evidence_snapshot
    if snapshot is None:
        return page.status in {PageStatus.EVIDENCE_READY, PageStatus.GENERATED}
    if snapshot.index_schema_version != INDEX_SCHEMA_VERSION or not page.evidence:
        return True
    for reference in page.evidence:
        chunk = chunks.get(reference.chunk_id)
        if (
            chunk is None
            or reference.content_hash is None
            or chunk.content_hash != reference.content_hash
            or chunk.path != reference.path
            or chunk.start_line != reference.start_line
            or chunk.end_line != reference.end_line
        ):
            return True
    return False


__all__ = [
    "stale_page_ids",
    "stale_page_ids_for_index",
    "validate_page_evidence",
]
