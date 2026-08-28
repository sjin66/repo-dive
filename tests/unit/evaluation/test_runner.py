from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from repo_dive.evaluation.runner import main, run_evaluations

FIXTURE = Path(__file__).parents[2] / "fixtures" / "index_repo"


def write_cases(path: Path) -> None:
    records = (
        {
            "id": "spec.future",
            "category": "specification",
            "prompt": "Future behavior",
            "expected_behavior": "Recorded but not executed.",
            "mode": "specification",
        },
        {
            "id": "search.greet",
            "category": "search",
            "prompt": "Find greet",
            "expected_behavior": "Find src/app.py and src.app.greet.",
            "mode": "executable",
            "evaluation": {
                "operation": "search",
                "repository": str(FIXTURE),
                "query": "greet",
                "max_results": 5,
                "expected": {
                    "paths": ["src/app.py"],
                    "symbols": ["src.app.greet"],
                    "citations": [],
                },
                "minimums": {
                    "recall_at_k": 1.0,
                    "mrr": 1.0,
                    "path_hit_rate": 1.0,
                    "symbol_hit_rate": 1.0,
                },
            },
        },
        {
            "id": "context.greet",
            "category": "context",
            "prompt": "Pack greet evidence",
            "expected_behavior": "Stay in budget and cite src/app.py.",
            "mode": "executable",
            "evaluation": {
                "operation": "context",
                "repository": str(FIXTURE),
                "query": "greet",
                "max_results": 5,
                "token_budget": 1200,
                "expected": {
                    "paths": ["src/app.py"],
                    "symbols": ["src.app.greet"],
                    "citations": ["src/app.py"],
                },
                "minimums": {
                    "budget_compliance": 1.0,
                    "citation_coverage": 1.0,
                },
            },
        },
    )
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_runner_separates_specifications_and_aggregates_executable_metrics(
    tmp_path: Path,
) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    write_cases(cases / "rag.jsonl")

    report = run_evaluations(cases)

    document = cast(dict[str, Any], report)
    assert document["schema_version"] == "1.0"
    assert document["runner_version"] == "1"
    assert document["summary"] == {
        "executable": 2,
        "failed": 0,
        "passed": 2,
        "specification": 1,
        "total": 3,
    }
    statuses = {case["id"]: case["status"] for case in document["cases"]}
    assert statuses == {
        "context.greet": "passed",
        "search.greet": "passed",
        "spec.future": "specification",
    }
    assert document["metrics"]["recall_at_k"] == {
        "evaluated_cases": 2,
        "mean": 1.0,
    }
    assert document["metrics"]["citation_coverage"] == {
        "evaluated_cases": 1,
        "mean": 1.0,
    }


def test_runner_main_emits_one_versioned_json_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    write_cases(cases / "rag.jsonl")

    assert main([str(cases), "--format", "json"]) == 0

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["schema_version"] == "1.0"
    assert captured.out.endswith("\n")
    assert captured.err == ""


def test_runner_reports_threshold_failure_per_case(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    record = {
        "id": "search.missing",
        "category": "search",
        "prompt": "Find absent evidence",
        "expected_behavior": "Expose a failed recall threshold.",
        "mode": "executable",
        "evaluation": {
            "operation": "search",
            "repository": str(FIXTURE),
            "query": "greet",
            "max_results": 5,
            "expected": {
                "paths": ["missing.py"],
                "symbols": [],
                "citations": [],
            },
            "minimums": {"recall_at_k": 1.0},
        },
    }
    (cases / "failed.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    report = cast(dict[str, Any], run_evaluations(cases))

    assert report["summary"]["failed"] == 1
    assert report["cases"][0]["status"] == "failed"
    assert report["cases"][0]["diagnostics"] == ["metric_below_minimum:recall_at_k"]
