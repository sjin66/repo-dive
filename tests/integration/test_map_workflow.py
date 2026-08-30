from __future__ import annotations

from pathlib import Path

from repo_dive.indexing.service import IndexService
from repo_dive.knowledge_map.build import KnowledgeMapBuildService
from repo_dive.knowledge_map.models import MapBuildBudgets
from repo_dive.knowledge_map.store import MapStore
from repo_dive.knowledge_map.views import project_architecture


def test_deterministic_build_validate_domain_and_project(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text(
        "def main():\n    helper()\n\ndef helper():\n    return 1\n",
        encoding="utf-8",
    )
    IndexService().build(repository)

    built = KnowledgeMapBuildService().build(repository, budgets=_budgets())
    artifact = MapStore(repository).read_artifact()
    projection = project_architecture(artifact, max_results=10)

    assert built.artifact == artifact
    assert artifact.evidence_snapshots == ()
    assert artifact.enrichments == ()
    assert projection["deterministic_revision"] == artifact.deterministic_revision


def _budgets() -> MapBuildBudgets:
    values = [1_000, 2_000_000, 1_000, 3_000, 32, 8, 100, 1, 100, 5, 30, 29, 100]
    capacities = [200, 128, 1_000, 32, 32, 32, 32, 16, 1_000_000]
    return MapBuildBudgets(*values, *capacities)  # type: ignore[arg-type]
