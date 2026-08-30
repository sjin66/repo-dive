from __future__ import annotations

import gc
import tracemalloc
from pathlib import Path
from typing import Any

import pytest

from repo_dive.commands.index import DEFAULT_MAX_CHUNK_LINES
from repo_dive.context import EvidencePacker
from repo_dive.indexing.service import IndexService
from repo_dive.retrieval.service import (
    DEFAULT_MAX_RESULTS,
    MAX_CANDIDATES,
    MAX_RESULTS,
    RepositorySearchResult,
    search_repository,
)
from repo_dive.scanner.service import DEFAULT_MAX_FILE_SIZE
from repo_dive.wiki.service import WikiService, structure_from_document


def generate_repository(root: Path, *, file_count: int) -> None:
    root.mkdir()
    for file_index in range(file_count):
        path = root / "src" / f"service_{file_index:04d}.py"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            f"def shared_marker_{file_index}(value: int) -> int:\n"
            f"    return value + {file_index}\n",
            encoding="utf-8",
        )


def measured_search(repository: Path) -> tuple[RepositorySearchResult, int]:
    gc.collect()
    tracemalloc.start()
    try:
        result = search_repository(repository, "shared marker", max_results=10)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak_bytes


def wiki_structure() -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "title": "Scale Wiki",
        "description": "Runtime-generated performance fixture.",
        "output_language": "en",
        "sections": [
            {
                "id": "guide",
                "title": "Guide",
                "pages": [
                    {
                        "id": "overview",
                        "title": "Overview",
                        "description": "Explain the shared marker service.",
                        "relevant_files": ["src/service_0000.py"],
                        "related_page_ids": [],
                        "subsections": [
                            {
                                "id": "runtime_flow",
                                "title": "Runtime flow",
                                "description": (
                                    "Explain the shared marker service flow."
                                ),
                                "direct_source_paths": ["src/service_0000.py"],
                                "documentation_only": False,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_retrieval_memory_trend_is_linear_and_return_count_is_constant(
    tmp_path: Path,
) -> None:
    small_repository = tmp_path / "small"
    large_repository = tmp_path / "large"
    generate_repository(small_repository, file_count=20)
    generate_repository(large_repository, file_count=80)
    IndexService().build(small_repository)
    IndexService().build(large_repository)

    small, small_peak = measured_search(small_repository)
    large, large_peak = measured_search(large_repository)
    small_bundle = EvidencePacker().pack(
        "shared marker", small.fusion.hits, token_budget=800
    )
    large_bundle = EvidencePacker().pack(
        "shared marker", large.fusion.hits, token_budget=800
    )

    assert len(small.fusion.hits) == len(large.fusion.hits) == 10
    assert len(small.symbols) <= 10
    assert len(large.symbols) <= 10
    assert len(small_bundle.items) <= 10
    assert len(large_bundle.items) <= 10
    assert small_bundle.estimated_tokens <= small_bundle.token_budget == 800
    assert large_bundle.estimated_tokens <= large_bundle.token_budget == 800
    assert large_peak <= small_peak * 6


@pytest.mark.parametrize("max_results", [1, DEFAULT_MAX_RESULTS, MAX_RESULTS])
def test_search_and_context_collections_obey_public_bounds(
    tmp_path: Path,
    max_results: int,
) -> None:
    repository = tmp_path / "repository"
    generate_repository(repository, file_count=80)
    IndexService().build(repository)

    retrieved = search_repository(
        repository,
        "shared marker",
        max_results=max_results,
    )
    bundle = EvidencePacker().pack(
        "shared marker",
        retrieved.fusion.hits,
        token_budget=800,
    )

    assert len(retrieved.fusion.hits) <= max_results <= MAX_RESULTS
    assert len(retrieved.symbols) <= max_results
    assert len(bundle.items) <= max_results
    assert len(bundle.items) + len(bundle.excluded) <= max_results
    assert bundle.estimated_tokens <= bundle.token_budget == 800


@pytest.mark.parametrize("file_count", [20, 80])
def test_wiki_evidence_reuses_search_and_context_limits_across_corpus_sizes(
    tmp_path: Path,
    file_count: int,
) -> None:
    repository = tmp_path / "repository"
    generate_repository(repository, file_count=file_count)
    IndexService().build(repository)
    service = WikiService(repository, clock=lambda: "2026-08-29T00:00:00Z")
    service.apply_structure(structure_from_document(wiki_structure()))

    update = service.collect_evidence(
        "overview",
        token_budget=800,
        max_results=MAX_RESULTS,
    )

    snapshot = update.page.evidence_snapshot
    assert snapshot is not None
    assert len(update.page.evidence) <= MAX_RESULTS
    assert len(update.bundle.items) <= MAX_RESULTS
    assert update.bundle.estimated_tokens <= update.bundle.token_budget == 800
    assert snapshot.estimated_tokens <= snapshot.token_budget == 800


def test_documented_default_and_hard_result_limits_are_internally_consistent() -> None:
    assert DEFAULT_MAX_FILE_SIZE == 1_000_000
    assert DEFAULT_MAX_CHUNK_LINES == 200
    assert DEFAULT_MAX_RESULTS == 10
    assert MAX_RESULTS == 50
    assert MAX_CANDIDATES == 200
