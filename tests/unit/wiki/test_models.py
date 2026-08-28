from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from repo_dive.schema import JsonObject
from repo_dive.wiki.models import (
    METADATA_SCHEMA_VERSION,
    WIKI_SCHEMA_VERSION,
    EvidenceRef,
    EvidenceSnapshot,
    Metadata,
    Page,
    PageStatus,
    RetrievalParameters,
    Section,
    Wiki,
    metadata_from_document,
    wiki_from_document,
)


def evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="evidence:one",
        chunk_id="chunk:one",
        path="src/app.py",
        start_line=2,
        end_line=5,
        content_hash="chunk-hash-1",
    )


def evidence_snapshot() -> EvidenceSnapshot:
    return EvidenceSnapshot(
        query="Overview Explain the repository entrypoint. path:src/app.py",
        repository_fingerprint="fingerprint-1",
        index_schema_version=3,
        index_build_id="build-1",
        token_budget=1_200,
        estimated_tokens=320,
        reserved_tokens=80,
        estimator="conservative_utf8_bytes_v1",
        truncated=False,
        retrieval=RetrievalParameters(
            max_results=5,
            strategy="weighted_rrf",
            rrf_k=60,
            channel_weights=(("lexical", 1.0), ("structural", 1.0)),
            overlap_threshold=0.8,
        ),
        generated_at="2026-08-28T01:00:00Z",
    )


def page(*, status: PageStatus = PageStatus.PENDING) -> Page:
    return Page(
        id="overview",
        title="Overview",
        description="Explain the repository entrypoint.",
        status=status,
        relevant_files=("src/app.py",),
        related_page_ids=(),
        evidence=(evidence(),),
        body="# Overview\n",
        error=None,
    )


def wiki() -> Wiki:
    return Wiki(
        title="Example Wiki",
        description="Grounded repository documentation.",
        sections=(
            Section(
                id="architecture",
                title="Architecture",
                pages=(page(),),
            ),
        ),
    )


def metadata() -> Metadata:
    return Metadata(
        repository="/workspace/example",
        repository_fingerprint="fingerprint-1",
        source_commit=None,
        output_language="en",
        index_schema_version=3,
        index_build_id="build-1",
        created_at="2026-08-28T00:00:00Z",
        updated_at="2026-08-28T00:00:00Z",
    )


def test_wiki_and_metadata_round_trip_with_independent_versions() -> None:
    expected_page = replace(page(), evidence_snapshot=evidence_snapshot())
    expected_wiki = replace(
        wiki(),
        sections=(replace(wiki().sections[0], pages=(expected_page,)),),
    )
    expected_metadata = metadata()

    wiki_document = expected_wiki.to_document()
    metadata_document = expected_metadata.to_document()

    assert wiki_document["schema_version"] == WIKI_SCHEMA_VERSION
    assert evidence().to_document()["evidence_id"] == "evidence:one"
    assert evidence().to_document()["content_hash"] == "chunk-hash-1"
    sections = cast(list[JsonObject], wiki_document["sections"])
    pages = cast(list[JsonObject], sections[0]["pages"])
    page_document = pages[0]
    snapshot_document = cast(JsonObject, page_document["evidence_snapshot"])
    assert snapshot_document["retrieval"] == {
        "channel_weights": {"lexical": 1.0, "structural": 1.0},
        "max_results": 5,
        "overlap_threshold": 0.8,
        "rrf_k": 60,
        "strategy": "weighted_rrf",
    }
    assert metadata_document["schema_version"] == METADATA_SCHEMA_VERSION
    assert metadata_document["wiki_schema_version"] == WIKI_SCHEMA_VERSION
    assert metadata_document["index_schema_version"] == 3
    assert metadata_document["index_build_id"] == "build-1"
    assert wiki_from_document(wiki_document) == expected_wiki
    assert metadata_from_document(metadata_document) == expected_metadata


def test_wiki_decoder_accepts_pre_evidence_optional_fields() -> None:
    document = wiki().to_document()
    sections = cast(list[JsonObject], document["sections"])
    pages = cast(list[JsonObject], sections[0]["pages"])
    page_document = pages[0]
    del page_document["evidence_snapshot"]
    evidence_documents = cast(list[JsonObject], page_document["evidence"])
    del evidence_documents[0]["content_hash"]

    decoded = wiki_from_document(document)

    decoded_page = decoded.sections[0].pages[0]
    assert decoded_page.evidence_snapshot is None
    assert decoded_page.evidence[0].content_hash is None


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PageStatus.PENDING, PageStatus.EVIDENCE_READY),
        (PageStatus.PENDING, PageStatus.FAILED),
        (PageStatus.EVIDENCE_READY, PageStatus.GENERATED),
        (PageStatus.EVIDENCE_READY, PageStatus.PENDING),
        (PageStatus.EVIDENCE_READY, PageStatus.FAILED),
        (PageStatus.GENERATED, PageStatus.PENDING),
        (PageStatus.GENERATED, PageStatus.FAILED),
        (PageStatus.FAILED, PageStatus.PENDING),
    ],
)
def test_page_allows_only_documented_state_transitions(
    current: PageStatus,
    target: PageStatus,
) -> None:
    original = page(status=current)

    transitioned = original.transition_to(target)

    assert transitioned.status is target
    assert original.status is current


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PageStatus.PENDING, PageStatus.GENERATED),
        (PageStatus.PENDING, PageStatus.PENDING),
        (PageStatus.EVIDENCE_READY, PageStatus.EVIDENCE_READY),
        (PageStatus.GENERATED, PageStatus.EVIDENCE_READY),
        (PageStatus.GENERATED, PageStatus.GENERATED),
        (PageStatus.FAILED, PageStatus.EVIDENCE_READY),
        (PageStatus.FAILED, PageStatus.GENERATED),
        (PageStatus.FAILED, PageStatus.FAILED),
    ],
)
def test_page_rejects_undocumented_state_transitions(
    current: PageStatus,
    target: PageStatus,
) -> None:
    with pytest.raises(ValueError, match="transition"):
        page(status=current).transition_to(target)


def test_wiki_rejects_duplicate_ids_and_invalid_evidence_locations() -> None:
    duplicate = replace(page(), title="Duplicate")
    with pytest.raises(ValueError, match="page IDs"):
        Wiki(
            title="Wiki",
            description="Description",
            sections=(
                Section(id="one", title="One", pages=(page(),)),
                Section(id="two", title="Two", pages=(duplicate,)),
            ),
        )

    with pytest.raises(ValueError, match="repository-relative POSIX"):
        replace(evidence(), path="../outside.py")
    with pytest.raises(ValueError, match="line range"):
        replace(evidence(), start_line=0)


def test_decoders_reject_missing_and_unknown_required_structure() -> None:
    wiki_document = wiki().to_document()
    del wiki_document["title"]
    with pytest.raises(ValueError, match="Wiki document fields"):
        wiki_from_document(wiki_document)

    metadata_document = metadata().to_document()
    del metadata_document["index_build_id"]
    with pytest.raises(ValueError, match="Metadata document fields"):
        metadata_from_document(metadata_document)

    unknown = wiki().to_document()
    unknown["unexpected"] = True
    with pytest.raises(ValueError, match="Wiki document fields"):
        wiki_from_document(unknown)


def test_metadata_requires_an_absolute_repository_identity() -> None:
    with pytest.raises(ValueError, match="absolute"):
        replace(metadata(), repository="relative/repository")
