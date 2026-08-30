from __future__ import annotations

import json
from pathlib import Path
from typing import NoReturn

import pytest

from repo_dive.cli import main
from repo_dive.commands import Command
from repo_dive.commands.map import MAP_COMMAND
from repo_dive.errors import InternalOperationError, RepositoryError
from repo_dive.indexing.service import IndexService
from repo_dive.schema import JsonObject

COMMAND_ARGUMENTS = {
    "build": [
        "--source-fact-budget",
        "1",
        "--artifact-byte-budget",
        "1",
        "--budget-file",
        "budget.json",
    ],
    "show": ["--view", "architecture", "--max-results", "1"],
    "evidence": ["--scope", "scope:test", "--token-budget", "1"],
    "enrich": ["--input", "submission.json"],
    "reset": ["--scope", "scope:test"],
    "validate": [],
}

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
    (
        "knowledge_map_validation_failed",
        3,
        "after_recovery",
        "rebuild_or_reset_scope",
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
    "knowledge_map_evidence_conflict": ("evidence",),
    "knowledge_map_evidence_not_found": ("enrich",),
    "knowledge_map_evidence_stale": ("evidence", "enrich"),
    "knowledge_map_enrichment_reference_invalid": ("enrich",),
    "knowledge_map_enrichment_budget_exceeded": ("enrich",),
    "knowledge_map_validation_failed": ("validate",),
}

SHARED_PROCESS_CASES = tuple(
    (command, code, exit_code, retry_mode, recovery_action)
    for code, exit_code, retry_mode, recovery_action in SHARED_ERROR_ROWS
    for command in ERROR_COMMANDS[code]
)


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
) -> None:
    """Pin every checked shared matrix cell at the process serialization boundary."""
    repository = tmp_path / f"{subcommand}-{code}"
    artifact = repository / ".repo-dive" / "knowledge-map.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"last-valid-artifact\n")
    before = artifact.read_bytes()

    def raise_contract_error(_args: object) -> NoReturn:
        error_type = InternalOperationError if exit_code == 4 else RepositoryError
        details: JsonObject | None = None
        if code.startswith("knowledge_map_"):
            details = {
                "recovery_action": recovery_action,
                "retry_mode": retry_mode,
            }
        raise error_type(code, "Safe map diagnostic.", details=details)

    command = Command(
        name=MAP_COMMAND.name,
        help=MAP_COMMAND.help,
        configure=MAP_COMMAND.configure,
        handler=raise_contract_error,
    )
    result = main(
        [
            "map",
            subcommand,
            str(repository),
            *COMMAND_ARGUMENTS[subcommand],
            "--format",
            "json",
        ],
        commands=(command,),
    )

    assert result == exit_code
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert captured.out.count("\n") == 1
    assert document["schema_version"] == "1.0"
    assert document["command"] == f"map {subcommand}"
    assert document["error"]["code"] == code
    assert document["error"]["details"] == {
        "recovery_action": recovery_action,
        "retry_mode": retry_mode,
    }
    assert captured.err == "Safe map diagnostic.\n"
    assert "\x1b[" not in captured.out + captured.err
    assert str(repository) not in captured.out + captured.err
    assert artifact.read_bytes() == before


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
    assert captured.out == ""
    assert "\x1b[" not in captured.err
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
