from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from repo_dive.cli import main
from repo_dive.commands.map import MAX_BUDGET_INPUT_BYTES
from repo_dive.indexing.service import IndexService
from repo_dive.knowledge_map.store import MAP_ARTIFACT_PATH
from repo_dive.knowledge_map.submission import ENRICHMENT_READER_CEILING


def test_map_help_exposes_only_the_six_supported_subcommands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["map", "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "{build,show,evidence,enrich,reset,validate}" in output
    for command in ("build", "show", "evidence", "enrich", "reset", "validate"):
        assert command in output
    assert "graph" not in output
    assert "status" not in output


def test_map_build_show_validate_json_workflow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text(
        "def main():\n    helper()\n\ndef helper():\n    return 1\n",
        encoding="utf-8",
    )
    (repository / "budgets.json").write_text(
        json.dumps(_budget_document()), encoding="utf-8"
    )
    IndexService().build(repository)

    assert (
        main(
            [
                "map",
                "build",
                str(repository),
                "--source-fact-budget",
                "1000",
                "--artifact-byte-budget",
                "2000000",
                "--budget-file",
                "budgets.json",
                "--format",
                "json",
            ]
        )
        == 0
    )
    built = json.loads(capsys.readouterr().out)
    assert built["command"] == "map build"
    assert built["result"]["changed"] is True
    artifact = repository / MAP_ARTIFACT_PATH
    before = artifact.read_bytes()

    assert (
        main(
            [
                "map",
                "show",
                str(repository),
                "--view",
                "architecture",
                "--max-results",
                "2",
                "--format",
                "json",
            ]
        )
        == 0
    )
    shown = json.loads(capsys.readouterr().out)
    assert shown["command"] == "map show"
    assert shown["result"]["included_count"] <= 2
    assert artifact.read_bytes() == before

    assert main(["map", "validate", str(repository), "--format", "json"]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["command"] == "map validate"
    assert validated["result"]["valid"] is True
    assert validated["result"]["semantic_entailment_checked"] is False
    assert artifact.read_bytes() == before


def test_map_errors_include_closed_recovery_details(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()

    assert (
        main(
            [
                "map",
                "show",
                str(repository),
                "--view",
                "architecture",
                "--max-results",
                "1",
                "--format",
                "json",
            ]
        )
        == 3
    )
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["command"] == "map show"
    assert document["error"]["code"] == "index_not_found"
    assert document["error"]["details"]["retry_mode"] == "after_recovery"
    assert document["error"]["details"]["recovery_action"] == "index_repository"
    assert "\x1b[" not in captured.out + captured.err


def test_map_evidence_enrich_and_reset_json_workflow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text(
        "def main():\n    helper()\n\ndef helper():\n    return 1\n",
        encoding="utf-8",
    )
    (repository / "budgets.json").write_text(
        json.dumps(_budget_document()), encoding="utf-8"
    )
    IndexService().build(repository)
    assert _build_map(repository) == 0
    build = json.loads(capsys.readouterr().out)
    artifact_path = repository / MAP_ARTIFACT_PATH
    deterministic_bytes = artifact_path.read_bytes()

    assert _build_map(repository) == 0
    repeated_build = json.loads(capsys.readouterr().out)["result"]
    assert repeated_build["unchanged"] is True
    assert artifact_path.read_bytes() == deterministic_bytes

    assert (
        main(
            [
                "map",
                "show",
                str(repository),
                "--view",
                "tour",
                "--max-results",
                "10",
                "--format",
                "json",
            ]
        )
        == 0
    )
    tour = json.loads(capsys.readouterr().out)["result"]["items"]
    assert tour
    scope_id = tour[0]["id"]

    assert (
        main(
            [
                "map",
                "evidence",
                str(repository),
                "--scope",
                scope_id,
                "--token-budget",
                "10000",
                "--format",
                "json",
            ]
        )
        == 0
    )
    evidence = json.loads(capsys.readouterr().out)["result"]
    snapshot = evidence["snapshot"]
    assert evidence["sources"]
    evidence_bytes = artifact_path.read_bytes()

    assert (
        main(
            [
                "map",
                "evidence",
                str(repository),
                "--scope",
                scope_id,
                "--token-budget",
                "10000",
                "--format",
                "json",
            ]
        )
        == 0
    )
    repeated_evidence = json.loads(capsys.readouterr().out)["result"]
    assert repeated_evidence["unchanged"] is True
    assert artifact_path.read_bytes() == evidence_bytes

    submission = {
        "schema_version": "1.0",
        "scope_id": scope_id,
        "expected_artifact_revision": evidence["artifact_revision"],
        "records": [
            {
                "id": "reading_guidance:cli-tour",
                "kind": "reading_guidance",
                "claims": [
                    {
                        "kind": "reading_guidance",
                        "text": "Read the entrypoint before its helper.",
                        "fact_node_ids": [
                            snapshot["references"][0]["anchor_fact_node_ids"][0]
                        ],
                        "related_node_ids": [],
                        "evidence_ids": [snapshot["references"][0]["evidence_id"]],
                    }
                ],
            }
        ],
    }
    (repository / ".repo-dive" / "submission.json").write_text(
        json.dumps(submission), encoding="utf-8"
    )
    assert (
        main(
            [
                "map",
                "enrich",
                str(repository),
                "--input",
                ".repo-dive/submission.json",
                "--format",
                "json",
            ]
        )
        == 0
    )
    enriched = json.loads(capsys.readouterr().out)["result"]
    assert enriched["changed"] is True
    enrichment_bytes = artifact_path.read_bytes()

    assert (
        main(
            [
                "map",
                "enrich",
                str(repository),
                "--input",
                ".repo-dive/submission.json",
                "--format",
                "json",
            ]
        )
        == 0
    )
    repeated_enrichment = json.loads(capsys.readouterr().out)["result"]
    assert repeated_enrichment["unchanged"] is True
    assert artifact_path.read_bytes() == enrichment_bytes

    assert (
        main(
            [
                "map",
                "reset",
                str(repository),
                "--scope",
                scope_id,
                "--format",
                "json",
            ]
        )
        == 0
    )
    reset = json.loads(capsys.readouterr().out)["result"]
    assert reset["changed"] is True
    assert reset["artifact_revision"] > build["result"]["artifact_revision"]
    reset_bytes = artifact_path.read_bytes()

    assert (
        main(
            [
                "map",
                "reset",
                str(repository),
                "--scope",
                scope_id,
                "--format",
                "json",
            ]
        )
        == 0
    )
    repeated_reset = json.loads(capsys.readouterr().out)["result"]
    assert repeated_reset["unchanged"] is True
    assert artifact_path.read_bytes() == reset_bytes


def test_map_rejects_malformed_enrichment_before_missing_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "bad.json").write_bytes(b'{"schema_version":"1.0",}')

    assert (
        main(
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
        == 2
    )
    document = json.loads(capsys.readouterr().out)
    assert document["error"] == {
        "code": "knowledge_map_enrichment_invalid",
        "details": {
            "recovery_action": "correct_submission",
            "retry_mode": "after_recovery",
        },
        "message": "Knowledge Map enrichment input is invalid.",
    }


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        b'{"schema_version":"1.0","schema_version":"1.0"}',
        b'{"schema_version":NaN}',
    ],
    ids=("invalid-utf8", "duplicate-key", "non-standard-constant"),
)
def test_map_enrich_strict_payload_failures_use_the_enrichment_error(
    tmp_path: Path,
    payload: bytes,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "bad.json").write_bytes(payload)

    assert (
        main(
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
        == 2
    )
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["error"]["code"] == "knowledge_map_enrichment_invalid"
    assert document["error"]["details"] == {
        "recovery_action": "correct_submission",
        "retry_mode": "after_recovery",
    }
    assert "\x1b[" not in captured.out + captured.err


def test_map_enrich_stdin_obeys_the_same_strict_payload_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b'{"x":1,"x":2}')))

    assert (
        main(
            [
                "map",
                "enrich",
                str(repository),
                "--input",
                "-",
                "--format",
                "json",
            ]
        )
        == 2
    )
    document = json.loads(capsys.readouterr().out)
    assert document["error"]["code"] == "knowledge_map_enrichment_invalid"


def test_map_enrich_rejects_payload_above_reader_ceiling_before_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "oversized.json").write_bytes(b" " * (ENRICHMENT_READER_CEILING + 1))

    assert (
        main(
            [
                "map",
                "enrich",
                str(repository),
                "--input",
                "oversized.json",
                "--format",
                "json",
            ]
        )
        == 2
    )
    document = json.loads(capsys.readouterr().out)
    assert document["error"]["code"] == "knowledge_map_enrichment_invalid"


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        b'{"schema_version":"1.0","schema_version":"1.0"}',
        b'{"schema_version":NaN}',
        b" " * (MAX_BUDGET_INPUT_BYTES + 1),
    ],
    ids=("invalid-utf8", "duplicate-key", "non-standard-constant", "oversized"),
)
def test_map_build_strict_budget_failures_precede_missing_index(
    tmp_path: Path,
    payload: bytes,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "budgets.json").write_bytes(payload)

    assert (
        main(
            [
                "map",
                "build",
                str(repository),
                "--source-fact-budget",
                "1",
                "--artifact-byte-budget",
                "1",
                "--budget-file",
                "budgets.json",
                "--format",
                "json",
            ]
        )
        == 2
    )
    document = json.loads(capsys.readouterr().out)
    assert document["error"]["code"] == "invalid_invocation"
    assert document["error"]["details"] == {
        "recovery_action": "correct_invocation",
        "retry_mode": "after_recovery",
    }


def test_map_input_rejects_absolute_and_symlink_escapes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    external = tmp_path / "private-submission.json"
    external.write_text("{}", encoding="utf-8")
    (repository / "linked.json").symlink_to(external)

    for input_path in (str(external), "linked.json"):
        assert (
            main(
                [
                    "map",
                    "enrich",
                    str(repository),
                    "--input",
                    input_path,
                    "--format",
                    "json",
                ]
            )
            == 3
        )
        captured = capsys.readouterr()
        document = json.loads(captured.out)
        assert document["error"]["code"] == "path_outside_repository"
        assert str(external) not in captured.out + captured.err


def test_map_input_escape_is_repository_error_with_recovery(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()

    assert (
        main(
            [
                "map",
                "enrich",
                str(repository),
                "--input",
                "../escape.json",
                "--format",
                "json",
            ]
        )
        == 3
    )
    document = json.loads(capsys.readouterr().out)
    assert document["error"]["code"] == "path_outside_repository"
    assert document["error"]["details"]["retry_mode"] == "after_recovery"
    assert document["error"]["details"]["recovery_action"] == "select_repository_input"


def _build_map(repository: Path) -> int:
    return main(
        [
            "map",
            "build",
            str(repository),
            "--source-fact-budget",
            "1000",
            "--artifact-byte-budget",
            "2000000",
            "--budget-file",
            "budgets.json",
            "--format",
            "json",
        ]
    )


def _budget_document() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "node_budget": 1000,
        "edge_budget": 3000,
        "contributing_relationship_ids_per_edge": 32,
        "resolution_candidates_per_reference": 8,
        "cluster_budget": 100,
        "minimum_cluster_files": 1,
        "flow_budget": 100,
        "flow_depth": 5,
        "nodes_per_flow": 30,
        "edges_per_flow": 29,
        "tour_budget": 100,
        "evidence_snapshots": 200,
        "evidence_references_per_snapshot": 128,
        "enrichment_records": 1000,
        "records_per_scope": 32,
        "claims_per_record": 32,
        "fact_node_ids_per_claim": 32,
        "related_node_ids_per_claim": 32,
        "evidence_ids_per_claim": 16,
        "enrichment_input_bytes": 1000000,
    }
