from __future__ import annotations

import inspect
import json
import subprocess
import sys
import time
from dataclasses import fields, replace
from pathlib import Path
from typing import BinaryIO

import pytest

import repo_dive.commands.map as map_commands
import repo_dive.indexing.service as indexing_service
import repo_dive.knowledge_map.build as map_build
import repo_dive.knowledge_map.enrichment_service as map_enrichment
import repo_dive.knowledge_map.evidence_service as map_evidence
import repo_dive.knowledge_map.store as map_store
from repo_dive.cli import main
from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.indexing.service import (
    IndexService,
    PublishedIndex,
    load_published_index,
)
from repo_dive.knowledge_map.build import KnowledgeMapBuildService
from repo_dive.knowledge_map.enrichment_service import KnowledgeMapEnrichmentService
from repo_dive.knowledge_map.evidence_service import KnowledgeMapEvidenceService
from repo_dive.knowledge_map.models import (
    EvidenceSnapshot,
    KnowledgeMapArtifact,
    MapBuildBudgets,
    canonical_bytes,
)
from repo_dive.knowledge_map.store import MapStore
from repo_dive.schema import JsonObject

COMMAND_ARGUMENTS = {
    "build": (
        "--source-fact-budget",
        "1000",
        "--artifact-byte-budget",
        "2000000",
        "--budget-file",
        "budget.json",
    ),
    "show": ("--view", "architecture", "--max-results", "1"),
    "evidence": ("--scope", "scope:test", "--token-budget", "1"),
    "enrich": ("--input", ".repo-dive/submission.json"),
    "reset": ("--scope", "scope:test"),
    "validate": (),
}


def test_invalid_map_format_uses_one_json_error_document_in_subprocess(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "repo_dive",
            "map",
            "validate",
            str(tmp_path),
            "--format",
            "xml",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    document = json.loads(completed.stdout)
    assert completed.stdout.count("\n") == 1
    assert document["schema_version"] == "1.0"
    assert document["command"] == "map validate"
    assert document["error"]["code"] == "invalid_invocation"
    assert document["error"]["details"] == {
        "recovery_action": "correct_invocation",
        "retry_mode": "after_recovery",
    }
    assert completed.stderr
    assert "\x1b[" not in completed.stdout + completed.stderr
    assert str(tmp_path) not in completed.stdout + completed.stderr


def test_non_map_command_prefix_does_not_enable_json_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["maple"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err

    assert main(["maple", "--format", "json"]) == 2

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["command"] == "maple"
    assert "details" not in document["error"]
    assert captured.err


SHARED_ERROR_ROWS = (
    ("repository_not_found", 3, "after_recovery", "select_repository"),
    ("repository_unavailable", 3, "after_cause_clears", "wait_for_repository"),
    ("repository_not_directory", 3, "after_recovery", "select_repository"),
    ("index_not_found", 3, "after_recovery", "index_repository"),
    ("index_stale", 3, "after_recovery", "rebuild_index"),
    ("knowledge_map_locked", 3, "unchanged", "wait_for_writer"),
    ("knowledge_map_revision_conflict", 3, "after_reload", "reload_artifact"),
    ("knowledge_map_index_changed", 3, "unchanged", "rerun_current_index"),
    (
        "knowledge_map_write_failed",
        4,
        "after_cause_clears",
        "inspect_write_environment",
    ),
    ("knowledge_map_not_found", 3, "after_recovery", "build_map"),
    ("knowledge_map_stale", 3, "after_recovery", "rebuild_map"),
    (
        "knowledge_map_invalid",
        3,
        "after_recovery",
        "preserve_and_rebuild_map",
    ),
    (
        "internal_operation_failed",
        4,
        "after_cause_clears",
        "inspect_safe_diagnostic",
    ),
    (
        "knowledge_map_source_budget_exceeded",
        3,
        "after_recovery",
        "raise_source_budget_or_reduce_scope",
    ),
    ("knowledge_map_budget_exceeded", 3, "after_recovery", "raise_named_budget"),
    (
        "knowledge_map_artifact_budget_exceeded",
        3,
        "after_recovery",
        "raise_artifact_budget_or_lower_sublimits",
    ),
    (
        "knowledge_map_capacity_conflict",
        3,
        "after_recovery",
        "reset_or_restore_capacity",
    ),
    (
        "knowledge_map_derivation_failed",
        4,
        "after_cause_clears",
        "inspect_safe_diagnostic",
    ),
    (
        "knowledge_map_scope_not_found",
        3,
        "after_recovery",
        "select_current_scope",
    ),
    (
        "knowledge_map_evidence_budget_insufficient",
        3,
        "after_recovery",
        "raise_token_budget",
    ),
    (
        "knowledge_map_evidence_capacity_exceeded",
        3,
        "after_recovery",
        "reset_scope_or_raise_capacity",
    ),
    (
        "knowledge_map_evidence_unavailable",
        3,
        "after_recovery",
        "make_source_indexable_or_select_scope",
    ),
    (
        "knowledge_map_evidence_conflict",
        3,
        "after_recovery",
        "reset_scope_and_recollect",
    ),
    (
        "knowledge_map_evidence_not_found",
        3,
        "after_recovery",
        "collect_evidence",
    ),
    (
        "knowledge_map_evidence_stale",
        3,
        "after_recovery",
        "rebuild_reset_recollect",
    ),
    (
        "knowledge_map_enrichment_reference_invalid",
        3,
        "after_recovery",
        "regenerate_current_scope_submission",
    ),
    (
        "knowledge_map_enrichment_budget_exceeded",
        3,
        "after_recovery",
        "reduce_enrichment_or_raise_capacity",
    ),
)

ERROR_COMMANDS = {
    "repository_not_found": tuple(COMMAND_ARGUMENTS),
    "repository_unavailable": tuple(COMMAND_ARGUMENTS),
    "repository_not_directory": tuple(COMMAND_ARGUMENTS),
    "index_not_found": tuple(COMMAND_ARGUMENTS),
    "index_stale": tuple(COMMAND_ARGUMENTS),
    "knowledge_map_locked": ("build", "evidence", "enrich", "reset"),
    "knowledge_map_revision_conflict": ("build", "evidence", "enrich", "reset"),
    "knowledge_map_index_changed": ("build", "evidence", "enrich", "reset"),
    "knowledge_map_write_failed": ("build", "evidence", "enrich", "reset"),
    "knowledge_map_not_found": ("evidence", "enrich", "reset", "validate", "show"),
    "knowledge_map_stale": ("evidence", "enrich", "reset", "validate", "show"),
    "knowledge_map_invalid": ("evidence", "enrich", "reset", "validate", "show"),
    "internal_operation_failed": tuple(COMMAND_ARGUMENTS),
    "knowledge_map_source_budget_exceeded": ("build",),
    "knowledge_map_budget_exceeded": ("build",),
    "knowledge_map_artifact_budget_exceeded": ("build",),
    "knowledge_map_capacity_conflict": ("build",),
    "knowledge_map_derivation_failed": ("build",),
    "knowledge_map_scope_not_found": ("evidence", "reset"),
    "knowledge_map_evidence_budget_insufficient": ("evidence",),
    "knowledge_map_evidence_capacity_exceeded": ("evidence",),
    "knowledge_map_evidence_unavailable": ("evidence",),
    "knowledge_map_evidence_conflict": ("evidence",),
    "knowledge_map_evidence_not_found": ("enrich",),
    "knowledge_map_evidence_stale": ("evidence", "enrich", "validate"),
    "knowledge_map_enrichment_reference_invalid": ("enrich",),
    "knowledge_map_enrichment_budget_exceeded": ("enrich",),
}

# This is intentionally independent of ERROR_COMMANDS and SHARED_ERROR_ROWS. A change
# to case generation cannot silently redefine the reviewed public applicability set.
FROZEN_EXPECTED_ERROR_CELLS = frozenset(
    {
        *((command, "invalid_invocation") for command in COMMAND_ARGUMENTS),
        *(
            (command, code)
            for command in ("build", "enrich")
            for code in (
                "path_outside_repository",
                "repository_path_not_found",
                "repository_path_unavailable",
            )
        ),
        ("enrich", "knowledge_map_enrichment_invalid"),
        *(
            (command, code)
            for command in COMMAND_ARGUMENTS
            for code in (
                "repository_not_found",
                "repository_unavailable",
                "repository_not_directory",
                "index_not_found",
                "index_stale",
                "internal_operation_failed",
            )
        ),
        *(
            (command, code)
            for command in ("build", "evidence", "enrich", "reset")
            for code in (
                "knowledge_map_locked",
                "knowledge_map_revision_conflict",
                "knowledge_map_index_changed",
                "knowledge_map_write_failed",
            )
        ),
        *(
            (command, code)
            for command in ("evidence", "enrich", "reset", "validate", "show")
            for code in (
                "knowledge_map_not_found",
                "knowledge_map_stale",
                "knowledge_map_invalid",
            )
        ),
        *(
            ("build", code)
            for code in (
                "knowledge_map_source_budget_exceeded",
                "knowledge_map_budget_exceeded",
                "knowledge_map_artifact_budget_exceeded",
                "knowledge_map_capacity_conflict",
                "knowledge_map_derivation_failed",
            )
        ),
        ("evidence", "knowledge_map_scope_not_found"),
        ("reset", "knowledge_map_scope_not_found"),
        ("evidence", "knowledge_map_evidence_budget_insufficient"),
        ("evidence", "knowledge_map_evidence_capacity_exceeded"),
        ("evidence", "knowledge_map_evidence_unavailable"),
        ("evidence", "knowledge_map_evidence_conflict"),
        ("enrich", "knowledge_map_evidence_not_found"),
        ("evidence", "knowledge_map_evidence_stale"),
        ("enrich", "knowledge_map_evidence_stale"),
        ("validate", "knowledge_map_evidence_stale"),
        ("enrich", "knowledge_map_enrichment_reference_invalid"),
        ("enrich", "knowledge_map_enrichment_budget_exceeded"),
    }
)

SEPARATE_PROCESS_ERROR_CELLS = frozenset(
    {
        *((command, "invalid_invocation") for command in COMMAND_ARGUMENTS),
        *(
            (command, code)
            for command in ("build", "enrich")
            for code in (
                "path_outside_repository",
                "repository_path_not_found",
                "repository_path_unavailable",
            )
        ),
        ("enrich", "knowledge_map_enrichment_invalid"),
    }
)

SHARED_PROCESS_CASES = tuple(
    (command, code, exit_code, retry_mode, recovery_action)
    for code, exit_code, retry_mode, recovery_action in SHARED_ERROR_ROWS
    for command in ERROR_COMMANDS[code]
)


def test_generated_error_cells_match_the_frozen_reviewed_contract() -> None:
    generated = {
        (command, code)
        for command, code, _exit, _retry, _recovery in SHARED_PROCESS_CASES
    }
    assert generated | SEPARATE_PROCESS_ERROR_CELLS == FROZEN_EXPECTED_ERROR_CELLS
    assert generated.isdisjoint(SEPARATE_PROCESS_ERROR_CELLS)


@pytest.mark.parametrize("source_state", ["empty", "skipped"])
def test_unavailable_map_evidence_has_safe_exact_process_details(
    tmp_path: Path,
    source_state: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "private-name.py").write_text(
        "" if source_state == "empty" else "private source text\n",
        encoding="utf-8",
    )
    if source_state == "skipped":
        IndexService().build(repository, max_file_size=1)
    else:
        IndexService().build(repository)
    artifact = (
        KnowledgeMapBuildService().build(repository, budgets=_map_budgets()).artifact
    )
    nodes = {item.id: item for item in artifact.nodes}
    scope = next(
        item
        for item in artifact.scope_contracts
        if any(
            nodes[anchor_id].path == "private-name.py"
            for anchor_id in item.required_anchor_fact_node_ids
        )
    )
    anchor_id = next(
        anchor_id
        for anchor_id in scope.required_anchor_fact_node_ids
        if nodes[anchor_id].path == "private-name.py"
    )
    artifact_path = repository / ".repo-dive" / "knowledge-map.json"
    before = artifact_path.read_bytes()

    assert (
        main(
            [
                "map",
                "evidence",
                str(repository),
                "--scope",
                scope.scope_id,
                "--token-budget",
                "1",
                "--format",
                "json",
            ]
        )
        == 3
    )

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["error"]["code"] == "knowledge_map_evidence_unavailable"
    assert document["error"]["details"] == {
        "anchor_fact_node_id": anchor_id,
        "recovery_action": "make_source_indexable_or_select_scope",
        "retry_mode": "after_recovery",
        "scope_id": scope.scope_id,
    }
    assert "private-name.py" not in captured.out + captured.err
    assert "private source text" not in captured.out + captured.err
    assert artifact_path.read_bytes() == before


@pytest.mark.parametrize(
    ("subcommand", "code", "exit_code", "retry_mode", "recovery_action"),
    SHARED_PROCESS_CASES,
)
def test_shared_error_applicability_matrix_reaches_the_public_process_contract(
    tmp_path: Path,
    subcommand: str,
    code: str,
    exit_code: int,
    retry_mode: str,
    recovery_action: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin every checked cell while retaining the real public service entry path."""
    repository = tmp_path / f"{subcommand}-{code}"
    artifact = repository / ".repo-dive" / "knowledge-map.json"
    repository.mkdir(parents=True)
    (repository / "app.py").write_text(
        (
            ""
            if code == "knowledge_map_evidence_unavailable"
            else "def helper():\n    return 1\n\ndef main():\n    return helper()\n"
        ),
        encoding="utf-8",
    )
    budget_document = _budget_document()
    if code == "knowledge_map_budget_exceeded":
        budget_document["node_budget"] = 1
    elif code in {
        "knowledge_map_capacity_conflict",
        "knowledge_map_evidence_capacity_exceeded",
    }:
        budget_document["evidence_references_per_snapshot"] = 1
    (repository / "budget.json").write_text(
        json.dumps(budget_document), encoding="utf-8"
    )
    (repository / ".repo-dive").mkdir()
    (repository / ".repo-dive/submission.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "scope_id": "scope:test",
                "expected_artifact_revision": 1,
                "records": [
                    {
                        "id": "concept:process",
                        "kind": "concept",
                        "claims": [
                            {
                                "kind": "summary",
                                "text": "Safe process fixture.",
                                "fact_node_ids": ["node:test"],
                                "related_node_ids": [],
                                "evidence_ids": ["evidence:test"],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    before: bytes | None = None
    command_arguments = list(COMMAND_ARGUMENTS[subcommand])
    if code == "knowledge_map_source_budget_exceeded":
        command_arguments[1] = "1"
    elif code == "knowledge_map_artifact_budget_exceeded":
        command_arguments[3] = "1"

    def raise_contract_error(*_args: object, **_kwargs: object) -> None:
        error_type = InternalOperationError if exit_code == 4 else RepositoryError
        details: JsonObject | None = None
        if code.startswith("knowledge_map_"):
            details = {
                "recovery_action": recovery_action,
                "retry_mode": retry_mode,
            }
        raise error_type(code, "Safe map diagnostic.", details=details)

    if code == "repository_not_found":
        (repository / "app.py").unlink()
        (repository / "budget.json").unlink()
        (repository / ".repo-dive/submission.json").unlink()
        (repository / ".repo-dive").rmdir()
        repository.rmdir()
    elif code == "repository_not_directory":
        (repository / "app.py").unlink()
        (repository / "budget.json").unlink()
        (repository / ".repo-dive/submission.json").unlink()
        (repository / ".repo-dive").rmdir()
        repository.rmdir()
        repository.write_text("not a directory", encoding="utf-8")
    elif code == "repository_unavailable":
        monkeypatch.setattr(map_commands, "resolve_repository", raise_contract_error)
    else:
        if code != "index_not_found":
            IndexService().build(repository)
        if code != "index_not_found":
            setup_budgets = _map_budgets()
            if code == "knowledge_map_evidence_capacity_exceeded":
                setup_budgets = replace(
                    setup_budgets, evidence_references_per_snapshot=1
                )
            built = (
                KnowledgeMapBuildService()
                .build(repository, budgets=setup_budgets)
                .artifact
            )
            if code not in {"knowledge_map_not_found", "knowledge_map_invalid"}:
                scope = built.scope_contracts[0]
                collected = None
                if code not in {
                    "knowledge_map_evidence_capacity_exceeded",
                    "knowledge_map_evidence_unavailable",
                    "knowledge_map_evidence_not_found",
                }:
                    collected = KnowledgeMapEvidenceService().collect(
                        repository, scope_id=scope.scope_id, token_budget=10_000
                    )
                reference_id = (
                    collected.snapshot.references[0].evidence_id
                    if collected is not None
                    else "evidence:missing"
                )
                fact_node_id = scope.allowed_fact_node_ids[0]
                if code == "knowledge_map_enrichment_reference_invalid":
                    fact_node_id = "node:not-in-scope"
                claim = {
                    "kind": "summary",
                    "text": "Safe process fixture.",
                    "fact_node_ids": [fact_node_id],
                    "related_node_ids": [],
                    "evidence_ids": [reference_id],
                }
                claims = [claim]
                if code == "knowledge_map_enrichment_budget_exceeded":
                    claims = [
                        {**claim, "text": f"Bounded process fixture {index}."}
                        for index in range(11)
                    ]
                submission = {
                    "schema_version": "1.0",
                    "scope_id": scope.scope_id,
                    "expected_artifact_revision": (
                        collected.artifact.artifact_revision
                        if collected is not None
                        else built.artifact_revision
                    ),
                    "records": [
                        {
                            "id": f"{scope.allowed_record_kinds[0]}:process",
                            "kind": scope.allowed_record_kinds[0],
                            "claims": claims,
                        }
                    ],
                }
                (repository / ".repo-dive/submission.json").write_text(
                    json.dumps(submission), encoding="utf-8"
                )
                if subcommand == "evidence":
                    command_arguments = [
                        "--scope",
                        scope.scope_id,
                        "--token-budget",
                        "10000",
                    ]
                elif subcommand == "reset":
                    command_arguments = ["--scope", scope.scope_id]
                if code == "knowledge_map_evidence_conflict":
                    assert collected is not None
                    KnowledgeMapEnrichmentService().enrich(
                        repository,
                        payload=json.dumps(submission).encode("utf-8"),
                    )
                    command_arguments[-1] = "9000"
            if code == "knowledge_map_not_found":
                artifact.unlink()
            elif code == "knowledge_map_invalid":
                artifact.write_bytes(b"{invalid\n")
            elif code in {"index_stale", "knowledge_map_stale"}:
                (repository / "app.py").write_text("changed = True\n", encoding="utf-8")
                if code == "knowledge_map_stale":
                    IndexService().build(repository)

        if code == "knowledge_map_evidence_stale":
            assert collected is not None
            stale = _replace_snapshot_content_hash(
                collected.artifact,
                collected.snapshot,
                "sha256:stale",
            )
            store = MapStore(repository)
            with store.write_transaction(store.read_snapshot()) as transaction:
                transaction.commit(stale)

        if code == "knowledge_map_scope_not_found":
            command_arguments = (
                ["--scope", "scope:missing", "--token-budget", "10000"]
                if subcommand == "evidence"
                else ["--scope", "scope:missing"]
            )
        elif code == "knowledge_map_evidence_budget_insufficient":
            command_arguments[-1] = "1"

        if code not in {
            "index_not_found",
            "index_stale",
            "knowledge_map_not_found",
            "knowledge_map_stale",
            "knowledge_map_invalid",
            "knowledge_map_scope_not_found",
            "knowledge_map_evidence_budget_insufficient",
            "knowledge_map_evidence_capacity_exceeded",
            "knowledge_map_evidence_unavailable",
            "knowledge_map_evidence_conflict",
            "knowledge_map_evidence_not_found",
            "knowledge_map_evidence_stale",
            "knowledge_map_enrichment_reference_invalid",
            "knowledge_map_enrichment_budget_exceeded",
            "knowledge_map_source_budget_exceeded",
            "knowledge_map_budget_exceeded",
            "knowledge_map_artifact_budget_exceeded",
            "knowledge_map_capacity_conflict",
        }:
            if code == "knowledge_map_locked":
                monkeypatch.setattr(
                    map_store,
                    "_try_lock",
                    lambda _stream: (_ for _ in ()).throw(BlockingIOError()),
                )
                times = iter((0.0, 3.0))
                monkeypatch.setattr(time, "monotonic", lambda: next(times))
            elif code == "knowledge_map_revision_conflict":
                if subcommand == "build":
                    command_arguments[3] = "1999999"
                elif subcommand == "evidence":
                    command_arguments[-1] = "9000"
                concurrent = _next_artifact(MapStore(repository).read_artifact())
                before = canonical_bytes(concurrent.to_document()) + b"\n"
                original_try_lock = map_store._try_lock
                replaced = False

                def replace_after_lock(stream: BinaryIO) -> None:
                    nonlocal replaced
                    original_try_lock(stream)
                    if not replaced:
                        artifact.write_bytes(
                            canonical_bytes(concurrent.to_document()) + b"\n"
                        )
                        replaced = True

                monkeypatch.setattr(map_store, "_try_lock", replace_after_lock)
            elif code == "knowledge_map_index_changed":
                published = load_published_index(repository)
                changed = replace(
                    published,
                    manifest=replace(published.manifest, build_id="changed-build"),
                )
                calls = 0

                def load_with_race(_repository: object) -> PublishedIndex:
                    nonlocal calls
                    calls += 1
                    return published if calls == 1 else changed

                module = {
                    "build": map_build,
                    "evidence": map_evidence,
                    "enrich": map_enrichment,
                    "reset": map_enrichment,
                }[subcommand]
                monkeypatch.setattr(module, "load_published_index", load_with_race)
            elif code == "knowledge_map_write_failed":
                if subcommand == "build":
                    command_arguments[3] = "1999999"
                elif subcommand == "evidence":
                    command_arguments[-1] = "9000"

                def fail_atomic_write(*_args: object, **_kwargs: object) -> None:
                    raise InternalOperationError("atomic_write_failed", "failed")

                monkeypatch.setattr(map_store, "atomic_write_bytes", fail_atomic_write)
            elif code == "knowledge_map_derivation_failed":
                monkeypatch.setattr(
                    map_build,
                    "snapshot_from_published_index",
                    lambda *_args, **_kwargs: (_ for _ in ()).throw(
                        RuntimeError("derivation fixture")
                    ),
                )
            elif code == "internal_operation_failed":
                module = {
                    "build": map_build,
                    "evidence": map_evidence,
                    "enrich": map_enrichment,
                    "reset": map_enrichment,
                    "validate": map_enrichment,
                    "show": indexing_service,
                }[subcommand]
                monkeypatch.setattr(
                    module, "load_published_index", raise_contract_error
                )
    if artifact.exists() and before is None:
        before = artifact.read_bytes()
    result = main(
        [
            "map",
            subcommand,
            str(repository),
            *command_arguments,
            "--format",
            "json",
        ],
    )

    assert result == exit_code
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert captured.out.count("\n") == 1
    assert document["schema_version"] == "1.0"
    assert document["command"] == f"map {subcommand}"
    assert document["error"]["code"] == code
    assert document["error"]["details"]["recovery_action"] == recovery_action
    assert document["error"]["details"]["retry_mode"] == retry_mode
    assert captured.err
    assert "\x1b[" not in captured.out + captured.err
    assert str(repository) not in captured.out + captured.err
    if before is not None:
        assert artifact.read_bytes() == before
    else:
        assert not artifact.exists()


def test_error_matrix_does_not_replace_public_map_entry_methods() -> None:
    source = inspect.getsource(
        test_shared_error_applicability_matrix_reaches_the_public_process_contract
    )
    forbidden = (
        'MAP_COMMAND, "handler"',
        'KnowledgeMapBuildService, "build"',
        'KnowledgeMapEvidenceService, "collect"',
        'KnowledgeMapEnrichmentService, "enrich"',
        'KnowledgeMapEnrichmentService, "reset"',
        'KnowledgeMapEnrichmentService, "validate"',
    )
    assert not any(value in source for value in forbidden)


def test_under_lock_index_change_precedes_simultaneous_cas_conflict(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (repository / "budget.json").write_text(
        json.dumps(_budget_document()), encoding="utf-8"
    )
    IndexService().build(repository)
    initial = (
        KnowledgeMapBuildService().build(repository, budgets=_map_budgets()).artifact
    )
    artifact_path = repository / ".repo-dive" / "knowledge-map.json"
    concurrent = _next_artifact(initial)
    concurrent_bytes = canonical_bytes(concurrent.to_document()) + b"\n"

    published = load_published_index(repository)
    changed = replace(
        published,
        manifest=replace(published.manifest, build_id="changed-under-lock"),
    )
    load_calls = 0

    def load_with_index_race(_repository: object) -> PublishedIndex:
        nonlocal load_calls
        load_calls += 1
        return published if load_calls == 1 else changed

    original_try_lock = map_store._try_lock
    replaced = False

    def replace_artifact_after_lock(stream: BinaryIO) -> None:
        nonlocal replaced
        original_try_lock(stream)
        if not replaced:
            artifact_path.write_bytes(concurrent_bytes)
            replaced = True

    monkeypatch.setattr(map_build, "load_published_index", load_with_index_race)
    monkeypatch.setattr(map_store, "_try_lock", replace_artifact_after_lock)

    result = main(
        [
            "map",
            "build",
            str(repository),
            "--source-fact-budget",
            "1000",
            "--artifact-byte-budget",
            "1999999",
            "--budget-file",
            "budget.json",
            "--format",
            "json",
        ]
    )

    assert result == 3
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["error"] == {
        "code": "knowledge_map_index_changed",
        "details": {
            "recovery_action": "rerun_current_index",
            "retry_mode": "unchanged",
        },
        "message": "Published index changed while building the Knowledge Map.",
    }
    assert captured.err
    assert "\x1b[" not in captured.out + captured.err
    assert str(repository) not in captured.out + captured.err
    assert artifact_path.read_bytes() == concurrent_bytes


def _budget_document() -> JsonObject:
    return {
        "schema_version": "1.0",
        "node_budget": 100,
        "edge_budget": 100,
        "contributing_relationship_ids_per_edge": 8,
        "resolution_candidates_per_reference": 4,
        "cluster_budget": 20,
        "minimum_cluster_files": 1,
        "flow_budget": 20,
        "flow_depth": 5,
        "nodes_per_flow": 20,
        "edges_per_flow": 20,
        "tour_budget": 20,
        "evidence_snapshots": 20,
        "evidence_references_per_snapshot": 20,
        "enrichment_records": 20,
        "records_per_scope": 10,
        "claims_per_record": 10,
        "fact_node_ids_per_claim": 10,
        "related_node_ids_per_claim": 10,
        "evidence_ids_per_claim": 10,
        "enrichment_input_bytes": 10_000,
    }


def _map_budgets() -> MapBuildBudgets:
    return MapBuildBudgets.from_budget_document(
        _budget_document(),
        source_fact_budget=1_000,
        artifact_byte_budget=2_000_000,
    )


def _replace_snapshot_content_hash(
    artifact: KnowledgeMapArtifact,
    snapshot: EvidenceSnapshot,
    content_hash: str,
) -> KnowledgeMapArtifact:
    reference = replace(snapshot.references[0], content_hash=content_hash)
    snapshot_values = {
        item.name: getattr(snapshot, item.name)
        for item in fields(snapshot)
        if item.name not in {"references", "snapshot_hash"}
    }
    stale_snapshot = EvidenceSnapshot.create(
        **snapshot_values,
        references=(reference, *snapshot.references[1:]),
    )
    return KnowledgeMapArtifact.create(
        artifact_revision=artifact.artifact_revision + 1,
        source=artifact.source,
        derivation_parameters=artifact.derivation_parameters,
        capacity_limits=artifact.capacity_limits,
        coverage=artifact.coverage,
        nodes=artifact.nodes,
        edges=artifact.edges,
        cycle_groups=artifact.cycle_groups,
        clusters=artifact.clusters,
        layers=artifact.layers,
        flows=artifact.flows,
        tour=artifact.tour,
        scope_contracts=artifact.scope_contracts,
        evidence_snapshots=(stale_snapshot,),
        enrichments=artifact.enrichments,
    )


def _next_artifact(artifact: KnowledgeMapArtifact) -> KnowledgeMapArtifact:
    return KnowledgeMapArtifact.create(
        artifact_revision=artifact.artifact_revision + 1,
        source=artifact.source,
        derivation_parameters=artifact.derivation_parameters,
        capacity_limits=artifact.capacity_limits,
        coverage=artifact.coverage,
        nodes=artifact.nodes,
        edges=artifact.edges,
        cycle_groups=artifact.cycle_groups,
        clusters=artifact.clusters,
        layers=artifact.layers,
        flows=artifact.flows,
        tour=artifact.tour,
        scope_contracts=artifact.scope_contracts,
        evidence_snapshots=artifact.evidence_snapshots,
        enrichments=artifact.enrichments,
    )


@pytest.mark.parametrize("subcommand", tuple(COMMAND_ARGUMENTS))
def test_invalid_format_is_no_write_for_every_map_command(
    tmp_path: Path,
    subcommand: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / subcommand
    artifact = repository / ".repo-dive" / "knowledge-map.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"last-valid-artifact\n")
    before = artifact.read_bytes()

    assert (
        main(
            [
                "map",
                subcommand,
                str(repository),
                *COMMAND_ARGUMENTS[subcommand],
                "--format",
                "xml",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert captured.out.count("\n") == 1
    assert document["schema_version"] == "1.0"
    assert document["command"] == f"map {subcommand}"
    assert document["error"]["code"] == "invalid_invocation"
    assert document["error"]["details"] == {
        "recovery_action": "correct_invocation",
        "retry_mode": "after_recovery",
    }
    assert captured.err
    assert "\x1b[" not in captured.out + captured.err
    assert str(repository) not in captured.out + captured.err
    assert artifact.read_bytes() == before


@pytest.mark.parametrize("subcommand", ["build", "enrich"])
@pytest.mark.parametrize(
    ("condition", "code", "retry_mode", "recovery_action"),
    [
        (
            "outside",
            "path_outside_repository",
            "after_recovery",
            "select_repository_input",
        ),
        (
            "missing",
            "repository_path_not_found",
            "after_recovery",
            "select_existing_input",
        ),
        (
            "unavailable",
            "repository_path_unavailable",
            "after_cause_clears",
            "wait_for_input",
        ),
    ],
)
def test_map_input_path_error_cells_use_real_filesystem_dispatch(
    tmp_path: Path,
    subcommand: str,
    condition: str,
    code: str,
    retry_mode: str,
    recovery_action: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "repo"
    artifact = repository / ".repo-dive" / "knowledge-map.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"last-valid-artifact\n")
    before = artifact.read_bytes()
    if condition == "outside":
        (tmp_path / "outside.json").write_text("{}", encoding="utf-8")
        input_path = "../outside.json"
    elif condition == "missing":
        input_path = "missing.json"
    else:
        (repository / "input-dir").mkdir()
        input_path = "input-dir"
    operation_arguments = (
        [
            "--source-fact-budget",
            "1",
            "--artifact-byte-budget",
            "1",
            "--budget-file",
            input_path,
        ]
        if subcommand == "build"
        else ["--input", input_path]
    )

    result = main(
        [
            "map",
            subcommand,
            str(repository),
            *operation_arguments,
            "--format",
            "json",
        ]
    )

    assert result == 3
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert captured.out.count("\n") == 1
    assert document["schema_version"] == "1.0"
    assert document["command"] == f"map {subcommand}"
    assert document["error"]["code"] == code
    assert document["error"]["details"]["retry_mode"] == retry_mode
    assert document["error"]["details"]["recovery_action"] == recovery_action
    assert captured.err
    assert "\x1b[" not in captured.out + captured.err
    assert str(tmp_path) not in captured.out + captured.err
    assert artifact.read_bytes() == before


def test_malformed_enrichment_cell_uses_real_decoder_and_preserves_bytes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    artifact = repository / ".repo-dive" / "knowledge-map.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"last-valid-artifact\n")
    before = artifact.read_bytes()
    (repository / "bad.json").write_bytes(b'{"schema_version":"1.0",}')

    result = main(
        [
            "map",
            "enrich",
            str(repository),
            "--input",
            "bad.json",
            "--format",
            "json",
        ]
    )

    assert result == 2
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert captured.out.count("\n") == 1
    assert document["schema_version"] == "1.0"
    assert document["command"] == "map enrich"
    assert document["error"] == {
        "code": "knowledge_map_enrichment_invalid",
        "details": {
            "recovery_action": "correct_submission",
            "retry_mode": "after_recovery",
        },
        "message": "Knowledge Map enrichment input is invalid.",
    }
    assert captured.err
    assert "\x1b[" not in captured.out + captured.err
    assert str(repository) not in captured.out + captured.err
    assert artifact.read_bytes() == before


def test_map_missing_repository_diagnostic_does_not_leak_absolute_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "private-host-path" / "missing"

    assert (
        main(
            [
                "map",
                "validate",
                str(repository),
                "--format",
                "json",
            ]
        )
        == 3
    )

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["error"]["details"] == {
        "recovery_action": "select_repository",
        "retry_mode": "after_recovery",
    }
    assert str(tmp_path) not in captured.out + captured.err


@pytest.mark.parametrize(
    ("subcommand", "arguments"),
    [
        ("build", []),
        ("show", []),
        ("evidence", []),
        ("enrich", []),
        ("reset", []),
        ("validate", []),
    ],
)
def test_every_map_command_has_versioned_invocation_errors(
    subcommand: str,
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["map", subcommand, *arguments, "--format", "json"]) == 2

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["schema_version"] == "1.0"
    assert document["command"] == f"map {subcommand}"
    assert document["error"]["code"] == "invalid_invocation"
    assert document["error"]["details"] == {
        "recovery_action": "correct_invocation",
        "retry_mode": "after_recovery",
    }
    assert "\x1b[" not in captured.out + captured.err


@pytest.mark.parametrize(
    ("subcommand", "arguments"),
    [
        (
            "build",
            [
                "--source-fact-budget",
                "1",
                "--artifact-byte-budget",
                "1",
                "--budget-file",
                "missing.json",
            ],
        ),
        ("show", ["--view", "architecture", "--max-results", "1"]),
        ("evidence", ["--scope", "scope:missing", "--token-budget", "1"]),
        ("enrich", ["--input", "missing.json"]),
        ("reset", ["--scope", "scope:missing"]),
        ("validate", []),
    ],
)
def test_every_map_command_reports_missing_repository_with_recovery(
    tmp_path: Path,
    subcommand: str,
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing"
    assert (
        main(
            [
                "map",
                subcommand,
                str(missing),
                *arguments,
                "--format",
                "json",
            ]
        )
        == 3
    )

    document = json.loads(capsys.readouterr().out)
    assert document["error"]["code"] == "repository_not_found"
    assert document["error"]["details"]["retry_mode"] == "after_recovery"
    assert document["error"]["details"]["recovery_action"] == "select_repository"


@pytest.mark.parametrize(
    ("subcommand", "arguments"),
    [
        ("show", ["--view", "architecture", "--max-results", "1"]),
        ("evidence", ["--scope", "scope:missing", "--token-budget", "1"]),
        ("enrich", ["--input", ".repo-dive/submission.json"]),
        ("reset", ["--scope", "scope:missing"]),
        ("validate", []),
    ],
)
def test_map_readers_and_semantic_writers_require_an_artifact(
    tmp_path: Path,
    subcommand: str,
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / subcommand
    repository.mkdir()
    (repository / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    IndexService().build(repository)
    if subcommand == "enrich":
        (repository / ".repo-dive" / "submission.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "scope_id": "scope:missing",
                    "expected_artifact_revision": 1,
                    "records": [
                        {
                            "id": "concept:missing",
                            "kind": "concept",
                            "claims": [
                                {
                                    "kind": "summary",
                                    "text": "Missing map fixture.",
                                    "fact_node_ids": ["node:missing"],
                                    "related_node_ids": [],
                                    "evidence_ids": ["evidence:missing"],
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    assert (
        main(
            [
                "map",
                subcommand,
                str(repository),
                *arguments,
                "--format",
                "json",
            ]
        )
        == 3
    )
    document = json.loads(capsys.readouterr().out)
    assert document["error"]["code"] == "knowledge_map_not_found"
    assert document["error"]["details"] == {
        "recovery_action": "build_map",
        "retry_mode": "after_recovery",
    }
