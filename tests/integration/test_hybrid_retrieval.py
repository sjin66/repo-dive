from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest

from repo_dive.context import EvidencePacker
from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import IndexService
from repo_dive.indexing.vectors import EmbeddingIdentity
from repo_dive.retrieval.service import search_repository

FIXTURE = Path(__file__).parents[1] / "fixtures" / "index_repo"


class SemanticFakeProvider:
    def __init__(self, *, model: str = "semantic-v1") -> None:
        self.identity = EmbeddingIdentity(
            provider="fake",
            model=model,
            dimensions=2,
        )
        self.calls: list[tuple[str, ...]] = []

    def embed(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = 32,
    ) -> tuple[tuple[float, ...], ...]:
        ordered = tuple(texts)
        self.calls.append(ordered)
        return tuple(_semantic_vector(text) for text in ordered)


def _semantic_vector(text: str) -> tuple[float, float]:
    normalized = text.casefold()
    if (
        "format_name" in normalized
        or ".strip().title()" in normalized
        or "normalize a display label" in normalized
    ):
        return (1.0, 0.0)
    return (0.0, 1.0)


def copy_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(
        FIXTURE,
        repository,
        ignore=shutil.ignore_patterns(".repo-dive"),
    )
    return repository


def test_semantic_rewrite_is_recalled_by_vector_and_respects_context_budget(
    tmp_path: Path,
) -> None:
    repository = copy_fixture(tmp_path)
    provider = SemanticFakeProvider()
    built = IndexService().build(repository, embedding_provider=provider)

    lexical_only = search_repository(
        repository,
        "normalize a display label",
        max_results=1,
    )
    hybrid = search_repository(
        repository,
        "normalize a display label",
        max_results=3,
        embedding_provider=provider,
    )

    assert not any(hit.chunk.path == "src/utils.py" for hit in lexical_only.fusion.hits)
    semantic_hit = next(
        hit for hit in hybrid.fusion.hits if hit.chunk.path == "src/utils.py"
    )
    assert semantic_hit.lexical_score is None
    assert semantic_hit.structural_score is None
    assert semantic_hit.vector_score == pytest.approx(1.0)
    assert semantic_hit.fused_score > 0.0
    assert hybrid.vector is not None
    assert hybrid.vector.status == "ready"
    assert hybrid.vector.indexed_chunks == built.counts.chunks
    assert hybrid.vector.query_embeddings == 1
    assert dict(hybrid.fusion.metadata.channel_weights)["vector"] == 1.0

    bundle = EvidencePacker().pack(
        "normalize a display label",
        hybrid.fusion.hits,
        token_budget=600,
    )
    assert bundle.estimated_tokens <= bundle.token_budget
    assert any(item.hit.chunk.path == "src/utils.py" for item in bundle.items)


def test_vector_identity_mismatch_supports_strict_and_degraded_search(
    tmp_path: Path,
) -> None:
    repository = copy_fixture(tmp_path)
    IndexService().build(
        repository,
        embedding_provider=SemanticFakeProvider(model="semantic-v1"),
    )
    replacement = SemanticFakeProvider(model="semantic-v2")

    with pytest.raises(RepositoryError) as exc_info:
        search_repository(
            repository,
            "normalize a display label",
            embedding_provider=replacement,
            vector_failure="strict",
        )

    assert exc_info.value.code == "index_vector_identity_mismatch"

    degraded = search_repository(
        repository,
        "normalize a display label",
        embedding_provider=replacement,
        vector_failure="degraded",
    )

    assert degraded.vector is not None
    assert degraded.vector.status == "degraded"
    assert degraded.vector.failure_policy == "degraded"
    assert degraded.vector.error_code == "index_vector_identity_mismatch"
    assert degraded.vector.query_embeddings == 0
    assert "vector" not in dict(degraded.fusion.metadata.channel_weights)
