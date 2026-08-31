from __future__ import annotations

from pathlib import Path

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.indexing.service import IndexService, load_published_index
from repo_dive.knowledge_map.snapshot import snapshot_from_published_index


def test_snapshot_reads_stable_bounded_facts_without_source_text(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text(
        "def main():\n    helper()\n\ndef helper():\n    return 1\n",
        encoding="utf-8",
    )
    IndexService().build(repository)

    snapshot = snapshot_from_published_index(
        load_published_index(repository), source_fact_budget=100
    )

    assert tuple(file.path for file in snapshot.files) == ("app.py",)
    assert snapshot.source.index_build_id
    assert snapshot.coverage.symbols == len(snapshot.symbols)
    assert all(not hasattr(item, "text") for item in snapshot.symbols)


def test_snapshot_fails_instead_of_returning_partial_source_inventory(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    IndexService().build(repository)

    with pytest.raises(RepositoryError) as exc_info:
        snapshot_from_published_index(
            load_published_index(repository), source_fact_budget=1
        )

    assert exc_info.value.code == "knowledge_map_source_budget_exceeded"
