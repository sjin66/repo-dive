from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.indexing.manifest import read_manifest
from repo_dive.indexing.service import IndexService
from repo_dive.indexing.store import IndexStore
from repo_dive.parsing.models import ParseResult, create_relationship
from repo_dive.parsing.pipeline import ParsingPipeline
from repo_dive.scanner.models import SourceFile

FIXTURE = Path(__file__).parents[2] / "fixtures" / "index_repo"


class RecordingParser:
    def __init__(
        self,
        *,
        fail_path: str | None = None,
        max_chunk_lines: int = 200,
    ) -> None:
        self.calls: list[str] = []
        self.fail_path = fail_path
        self.delegate = ParsingPipeline(max_chunk_lines=max_chunk_lines)

    def parse(self, source: SourceFile) -> ParseResult:
        self.calls.append(source.record.path)
        if source.record.path == self.fail_path:
            raise RuntimeError("sensitive parser implementation detail")
        return self.delegate.parse(source)


class InvalidRelationshipParser:
    def __init__(self) -> None:
        self.delegate = ParsingPipeline()

    def parse(self, source: SourceFile) -> ParseResult:
        parsed = self.delegate.parse(source)
        if source.record.path != "src/app.py":
            return parsed
        return ParseResult(
            chunks=parsed.chunks,
            symbols=parsed.symbols,
            relationships=(
                create_relationship(
                    source_id=parsed.symbols[0].id,
                    target_id="symbol:missing",
                    kind="calls",
                    confidence=1.0,
                    source="test",
                ),
            ),
            diagnostics=parsed.diagnostics,
        )


def copy_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(
        FIXTURE,
        repository,
        ignore=shutil.ignore_patterns(".repo-dive"),
    )
    return repository


def chunk_ids(store: IndexStore) -> dict[str, tuple[str, ...]]:
    return {
        path: tuple(chunk.id for chunk in store.get_parse_result(path).chunks)
        for path in ("README.md", "src/app.py", "src/utils.py")
        if store.get_file(path) is not None
    }


def test_first_build_atomically_publishes_database_manifest_and_metadata(
    tmp_path: Path,
) -> None:
    repository = copy_fixture(tmp_path)

    result = IndexService().build(repository)

    index = repository / ".repo-dive" / "index"
    assert index.is_symlink()
    assert result.rebuilt_files == 3
    assert result.reused_files == 0
    assert result.deleted_files == 0
    assert (index / "index.sqlite3").is_file()
    assert (index / "manifest.json").is_file()
    assert (index / "metadata.json").is_file()
    assert read_manifest(index / "manifest.json").build_id == result.build_id
    assert (
        json.loads((index / "metadata.json").read_text(encoding="utf-8"))["index"][
            "build_id"
        ]
        == result.build_id
    )
    with IndexStore.open(index / "index.sqlite3") as store:
        assert store.foreign_key_violations() == ()
        assert store.integrity_check() == ("ok",)
    assert not list((repository / ".repo-dive").glob(".index.*.tmp"))
    assert not list((repository / ".repo-dive" / "index-generations").glob(".build-*"))


def test_incremental_build_reparses_only_changed_file_and_removes_deleted_file(
    tmp_path: Path,
) -> None:
    repository = copy_fixture(tmp_path)
    parser = RecordingParser()
    service = IndexService()
    first = service.build(repository, parser=parser)
    assert set(parser.calls) == {"README.md", "src/app.py", "src/utils.py"}
    with IndexStore.open(repository / ".repo-dive/index/index.sqlite3") as store:
        before = chunk_ids(store)

    parser.calls.clear()
    app = repository / "src" / "app.py"
    app.write_text(
        app.read_text(encoding="utf-8").replace("Hello,", "Welcome,"),
        encoding="utf-8",
    )

    second = service.build(repository, parser=parser)

    assert second.build_id != first.build_id
    assert parser.calls == ["src/app.py"]
    assert second.rebuilt_files == 1
    assert second.reused_files == 2
    assert second.deleted_files == 0
    with IndexStore.open(repository / ".repo-dive/index/index.sqlite3") as store:
        after_change = chunk_ids(store)
    assert after_change["src/app.py"] != before["src/app.py"]
    assert after_change["README.md"] == before["README.md"]
    assert after_change["src/utils.py"] == before["src/utils.py"]

    parser.calls.clear()
    (repository / "src" / "utils.py").unlink()

    third = service.build(repository, parser=parser)

    assert third.deleted_files == 1
    assert third.rebuilt_files == 0
    assert third.reused_files == 2
    assert parser.calls == []
    with IndexStore.open(repository / ".repo-dive/index/index.sqlite3") as store:
        assert store.get_file("src/utils.py") is None
        assert store.get_parse_result("src/app.py").chunks


def test_unchanged_build_reuses_current_generation_without_parsing(
    tmp_path: Path,
) -> None:
    repository = copy_fixture(tmp_path)
    parser = RecordingParser()
    service = IndexService()
    first = service.build(repository, parser=parser)
    parser.calls.clear()

    second = service.build(repository, parser=parser)

    assert second.build_id == first.build_id
    assert second.rebuilt_files == 0
    assert second.reused_files == 3
    assert second.deleted_files == 0
    assert parser.calls == []
    assert len(list((repository / ".repo-dive/index-generations").iterdir())) == 1


def test_build_parameter_change_forces_full_reparse(tmp_path: Path) -> None:
    repository = copy_fixture(tmp_path)
    service = IndexService()
    first = service.build(repository)
    parser = RecordingParser(max_chunk_lines=1)

    second = service.build(
        repository,
        max_chunk_lines=1,
        parser=parser,
    )

    assert second.build_id != first.build_id
    assert second.reused_files == 0
    assert second.rebuilt_files == 3
    assert set(parser.calls) == {"README.md", "src/app.py", "src/utils.py"}


def test_build_failure_preserves_old_generation_and_returns_safe_stage(
    tmp_path: Path,
) -> None:
    repository = copy_fixture(tmp_path)
    service = IndexService()
    first = service.build(repository)
    index = repository / ".repo-dive" / "index"
    original_generation = index.resolve(strict=True)
    app = repository / "src" / "app.py"
    app.write_text(
        app.read_text(encoding="utf-8") + "\nBROKEN = True\n", encoding="utf-8"
    )

    with pytest.raises(InternalOperationError) as exc_info:
        service.build(repository, parser=RecordingParser(fail_path="src/app.py"))

    assert exc_info.value.code == "index_build_failed"
    assert exc_info.value.message == "Could not build repository index."
    assert exc_info.value.details == {"stage": "parse", "path": "src/app.py"}
    assert "sensitive" not in str(exc_info.value.details)
    assert index.resolve(strict=True) == original_generation
    assert read_manifest(index / "manifest.json").build_id == first.build_id
    with IndexStore.open(index / "index.sqlite3") as store:
        assert store.integrity_check() == ("ok",)
    generations = repository / ".repo-dive" / "index-generations"
    assert len(list(generations.iterdir())) == 1


def test_publish_failure_preserves_old_generation_and_cleans_new_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = copy_fixture(tmp_path)
    service = IndexService()
    first = service.build(repository)
    index = repository / ".repo-dive" / "index"
    original_generation = index.resolve(strict=True)
    app = repository / "src" / "app.py"
    app.write_text(
        app.read_text(encoding="utf-8").replace("Hello,", "Welcome,"),
        encoding="utf-8",
    )
    real_replace = os.replace

    def fail_pointer_replace(source: str | Path, destination: str | Path) -> None:
        if Path(destination) == index:
            raise OSError("simulated pointer replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr("repo_dive.indexing.service.os.replace", fail_pointer_replace)

    with pytest.raises(InternalOperationError) as exc_info:
        service.build(repository)

    assert exc_info.value.code == "index_build_failed"
    assert exc_info.value.details == {"stage": "publish"}
    assert index.resolve(strict=True) == original_generation
    assert read_manifest(index / "manifest.json").build_id == first.build_id
    generations = repository / ".repo-dive" / "index-generations"
    assert list(generations.iterdir()) == [original_generation]
    assert not list((repository / ".repo-dive").glob(".index.*.tmp"))


def test_build_rejects_repo_dive_symlink_outside_repository(tmp_path: Path) -> None:
    repository = copy_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repository / ".repo-dive").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RepositoryError) as exc_info:
        IndexService().build(repository)

    assert exc_info.value.code == "path_outside_repository"
    assert list(outside.iterdir()) == []


def test_index_write_failure_reports_safe_stage_and_path(tmp_path: Path) -> None:
    repository = copy_fixture(tmp_path)

    with pytest.raises(InternalOperationError) as exc_info:
        IndexService().build(repository, parser=InvalidRelationshipParser())

    assert exc_info.value.code == "index_build_failed"
    assert exc_info.value.details == {"stage": "write", "path": "src/app.py"}
    assert not (repository / ".repo-dive" / "index").exists()
    generations = repository / ".repo-dive" / "index-generations"
    assert list(generations.iterdir()) == []


def test_build_rejects_tampered_current_metadata(tmp_path: Path) -> None:
    repository = copy_fixture(tmp_path)
    IndexService().build(repository)
    metadata = repository / ".repo-dive" / "index" / "metadata.json"
    document = json.loads(metadata.read_text(encoding="utf-8"))
    document["schema_version"] = "99.0"
    metadata.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RepositoryError) as exc_info:
        IndexService().build(repository)

    assert exc_info.value.code == "index_metadata_invalid"
