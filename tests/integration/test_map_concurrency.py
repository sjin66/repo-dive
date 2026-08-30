from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.knowledge_map.models import (
    KnowledgeMapArtifact,
    MapBuildBudgets,
    MapSource,
)
from repo_dive.knowledge_map.store import MapStore


def test_contested_writer_times_out_without_changing_previous_bytes(
    tmp_path: Path,
) -> None:
    store = MapStore(tmp_path)
    baseline = store.read_snapshot()
    candidate = KnowledgeMapArtifact.create_empty(
        source=MapSource("fingerprint", "build", 5, "non_git", None, None),
        budgets=_budgets(),
    )

    with store.write_transaction(baseline, lock_timeout=0.2) as first:
        with (
            pytest.raises(RepositoryError) as exc_info,
            store.write_transaction(baseline, lock_timeout=0.03),
        ):
            pass
        assert store.read_snapshot().state == "absent"
        first.commit(candidate)

    assert exc_info.value.code == "knowledge_map_locked"
    assert store.read_artifact() == candidate


def test_lock_contention_is_enforced_across_processes(tmp_path: Path) -> None:
    store = MapStore(tmp_path)
    snapshot = store.read_snapshot()
    script = """
import sys
from repo_dive.errors import RepositoryError
from repo_dive.knowledge_map.store import MapStore

store = MapStore(sys.argv[1])
try:
    with store.write_transaction(store.read_snapshot(), lock_timeout=0.05):
        pass
except RepositoryError as error:
    print(error.code)
"""

    with store.write_transaction(snapshot, lock_timeout=0.2):
        completed = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

    assert completed.stdout.strip() == "knowledge_map_locked"
    with store.write_transaction(store.read_snapshot(), lock_timeout=0.2):
        pass


def _budgets() -> MapBuildBudgets:
    values = [100, 100_000, 100, 100, 8, 4, 20, 1, 20, 5, 20, 20, 20]
    capacities = [20, 20, 20, 10, 10, 10, 10, 10, 10_000]
    return MapBuildBudgets(*values, *capacities)  # type: ignore[arg-type]
