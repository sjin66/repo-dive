from __future__ import annotations

from pathlib import Path

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import IndexService, load_published_index
from repo_dive.knowledge_map.snapshot import snapshot_from_published_index


def test_source_fact_budget_rejects_large_inventory_before_derivation(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    for index in range(50):
        (repository / f"module_{index}.py").write_text(
            f"def function_{index}():\n    return {index}\n", encoding="utf-8"
        )
    IndexService().build(repository)

    with pytest.raises(RepositoryError) as exc_info:
        snapshot_from_published_index(
            load_published_index(repository), source_fact_budget=10
        )

    assert exc_info.value.code == "knowledge_map_source_budget_exceeded"
