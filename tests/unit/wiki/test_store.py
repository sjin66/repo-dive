from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.wiki.models import (
    EvidenceRef,
    Metadata,
    Page,
    PageStatus,
    Section,
    Wiki,
)
from repo_dive.wiki.store import METADATA_PATH, WIKI_PATH, WikiStore


def wiki() -> Wiki:
    return Wiki(
        title="Example Wiki",
        description="Repository documentation.",
        sections=(
            Section(
                id="guide",
                title="Guide",
                pages=(
                    Page(
                        id="overview",
                        title="Overview",
                        description="Explain the entrypoint.",
                        status=PageStatus.EVIDENCE_READY,
                        relevant_files=("src/app.py",),
                        related_page_ids=(),
                        evidence=(
                            EvidenceRef(
                                evidence_id="evidence:one",
                                chunk_id="chunk:one",
                                path="src/app.py",
                                start_line=1,
                                end_line=3,
                            ),
                        ),
                        body=None,
                        error=None,
                    ),
                ),
            ),
        ),
    )


def metadata() -> Metadata:
    return Metadata(
        repository="/workspace/example",
        repository_fingerprint="fingerprint",
        source_commit="abc123",
        output_language="en",
        index_schema_version=3,
        index_build_id="build-1",
        created_at="2026-08-28T00:00:00Z",
        updated_at="2026-08-28T00:00:00Z",
    )


def test_store_round_trips_stable_public_artifacts(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    store = WikiStore(repository)

    wiki_path = store.write_wiki(wiki())
    metadata_path = store.write_metadata(metadata())

    assert wiki_path == repository / WIKI_PATH
    assert metadata_path == repository / METADATA_PATH
    assert wiki_path.read_text(encoding="utf-8").endswith("\n")
    assert metadata_path.read_text(encoding="utf-8").endswith("\n")
    assert store.read_wiki() == wiki()
    assert store.read_metadata() == metadata()
    assert json.loads(wiki_path.read_text(encoding="utf-8"))["title"] == (
        "Example Wiki"
    )


@pytest.mark.parametrize(
    ("relative_path", "reader", "error_code"),
    [
        (WIKI_PATH, "read_wiki", "wiki_state_invalid"),
        (METADATA_PATH, "read_metadata", "wiki_metadata_invalid"),
    ],
)
def test_store_rejects_corrupt_json_without_overwriting_it(
    tmp_path: Path,
    relative_path: str,
    reader: str,
    error_code: str,
) -> None:
    repository = tmp_path / "repository"
    target = repository / relative_path
    target.parent.mkdir(parents=True)
    original = b'{"schema_version":"1.0",broken\n'
    target.write_bytes(original)
    store = WikiStore(repository)

    with pytest.raises(RepositoryError) as exc_info:
        getattr(store, reader)()

    assert exc_info.value.code == error_code
    assert exc_info.value.details is None
    assert target.read_bytes() == original


@pytest.mark.parametrize(
    ("relative_path", "reader", "error_code"),
    [
        (WIKI_PATH, "read_wiki", "wiki_state_version_unsupported"),
        (
            METADATA_PATH,
            "read_metadata",
            "wiki_metadata_version_unsupported",
        ),
    ],
)
def test_store_reports_unknown_artifact_schema_versions(
    tmp_path: Path,
    relative_path: str,
    reader: str,
    error_code: str,
) -> None:
    repository = tmp_path / "repository"
    target = repository / relative_path
    target.parent.mkdir(parents=True)
    target.write_text('{"schema_version":"99.0"}\n', encoding="utf-8")

    with pytest.raises(RepositoryError) as exc_info:
        getattr(WikiStore(repository), reader)()

    assert exc_info.value.code == error_code
    assert exc_info.value.details == {"actual": "99.0", "expected": "1.0"}


@pytest.mark.parametrize(
    ("relative_path", "writer", "value"),
    [
        (WIKI_PATH, "write_wiki", wiki()),
        (METADATA_PATH, "write_metadata", metadata()),
    ],
)
def test_failed_atomic_write_preserves_existing_public_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
    writer: str,
    value: Wiki | Metadata,
) -> None:
    repository = tmp_path / "repository"
    target = repository / relative_path
    target.parent.mkdir(parents=True)
    original = b'{"old":"artifact"}\n'
    target.write_bytes(original)

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("repo_dive.storage.atomic.os.replace", fail_replace)

    with pytest.raises(InternalOperationError) as exc_info:
        getattr(WikiStore(repository), writer)(value)

    assert exc_info.value.code == "atomic_write_failed"
    assert target.read_bytes() == original
    assert list(target.parent.iterdir()) == [target]


def test_store_rejects_missing_required_fields_without_rewriting_file(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    target = repository / WIKI_PATH
    target.parent.mkdir(parents=True)
    original = b'{"schema_version":"1.0"}\n'
    target.write_bytes(original)

    with pytest.raises(RepositoryError) as exc_info:
        WikiStore(repository).read_wiki()

    assert exc_info.value.code == "wiki_state_invalid"
    assert target.read_bytes() == original
