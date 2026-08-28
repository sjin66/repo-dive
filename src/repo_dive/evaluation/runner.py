"""Executable RAG evaluation runner over isolated repository fixtures."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from repo_dive.context import EvidencePacker
from repo_dive.errors import RepoDiveError
from repo_dive.evaluation.metrics import (
    aggregate_metric,
    budget_compliance,
    citation_coverage,
    hit_rate,
    recall_at_k,
    reciprocal_rank,
)
from repo_dive.indexing.service import IndexService
from repo_dive.retrieval.service import search_repository
from repo_dive.schema import JsonObject, JsonValue, serialize_json_document

REPORT_SCHEMA_VERSION = "1.0"
RUNNER_VERSION = "1"
METRIC_NAMES = (
    "recall_at_k",
    "mrr",
    "path_hit_rate",
    "symbol_hit_rate",
    "budget_compliance",
    "citation_coverage",
)
CaseMode = Literal["executable", "specification"]
Operation = Literal["search", "context"]


class EvaluationConfigError(ValueError):
    """One safe error for invalid or ambiguous evaluation input."""


@dataclass(frozen=True, slots=True)
class _Evaluation:
    operation: Operation
    repository: Path
    query: str
    max_results: int
    token_budget: int | None
    expected_paths: tuple[str, ...]
    expected_symbols: tuple[str, ...]
    expected_citations: tuple[str, ...]
    minimums: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class _Case:
    id: str
    category: str
    mode: CaseMode
    source_path: str
    source_line: int
    evaluation: _Evaluation | None


def run_evaluations(path: str | Path) -> JsonObject:
    """Load, isolate, execute, and aggregate one evaluation corpus."""
    cases = _load_cases(Path(path))
    results = tuple(_evaluate_case(case) for case in cases)
    executable = tuple(case for case in results if case["status"] != "specification")
    metrics: JsonObject = {
        name: aggregate_metric(
            cast(float | None, cast(JsonObject, case["metrics"])[name])
            for case in executable
        )
        for name in METRIC_NAMES
    }
    summary: JsonObject = {
        "executable": len(executable),
        "failed": sum(case["status"] == "failed" for case in executable),
        "passed": sum(case["status"] == "passed" for case in executable),
        "specification": sum(case["status"] == "specification" for case in results),
        "total": len(results),
    }
    return {
        "cases": list(results),
        "metrics": metrics,
        "runner_version": RUNNER_VERSION,
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": summary,
    }


def _load_cases(path: Path) -> tuple[_Case, ...]:
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    if not files or any(not item.is_file() for item in files):
        raise EvaluationConfigError("evaluation path must contain JSONL files")
    cases: list[_Case] = []
    seen: set[str] = set()
    for file_path in files:
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            raise EvaluationConfigError("could not read evaluation cases") from error
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                document = _object(json.loads(line))
                case = _parse_case(document, file_path, line_number)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                raise EvaluationConfigError(
                    f"invalid evaluation case at {file_path}:{line_number}"
                ) from error
            if case.id in seen:
                raise EvaluationConfigError("evaluation case IDs must be unique")
            seen.add(case.id)
            cases.append(case)
    return tuple(sorted(cases, key=lambda case: case.id))


def _parse_case(document: JsonObject, path: Path, line: int) -> _Case:
    case_id = _string(document["id"])
    category = _string(document["category"])
    mode_value = _string(document["mode"])
    if mode_value not in ("executable", "specification"):
        raise ValueError("invalid evaluation mode")
    mode = cast(CaseMode, mode_value)
    evaluation = (
        _parse_evaluation(_object(document["evaluation"]))
        if mode == "executable"
        else None
    )
    if mode == "specification" and "evaluation" in document:
        raise ValueError("specification cases cannot contain evaluation config")
    return _Case(
        id=case_id,
        category=category,
        mode=mode,
        source_path=path.as_posix(),
        source_line=line,
        evaluation=evaluation,
    )


def _parse_evaluation(document: JsonObject) -> _Evaluation:
    operation_value = _string(document["operation"])
    if operation_value not in ("search", "context"):
        raise ValueError("unsupported evaluation operation")
    operation = cast(Operation, operation_value)
    expected = _object(document["expected"])
    maximum = _integer(document.get("max_results", 10))
    budget_value = document.get("token_budget")
    budget = _integer(budget_value) if budget_value is not None else None
    if maximum <= 0 or (operation == "context" and (budget is None or budget <= 0)):
        raise ValueError("evaluation limits must be positive")
    minimum_document = _object(document.get("minimums", {}))
    minimums: list[tuple[str, float]] = []
    for name, value in minimum_document.items():
        if name not in METRIC_NAMES:
            raise ValueError("unknown evaluation metric")
        minimum = _number(value)
        if not 0.0 <= minimum <= 1.0:
            raise ValueError("metric minimum must be between zero and one")
        minimums.append((name, minimum))
    return _Evaluation(
        operation=operation,
        repository=Path(_string(document["repository"])),
        query=_string(document["query"]),
        max_results=maximum,
        token_budget=budget,
        expected_paths=_strings(expected.get("paths", [])),
        expected_symbols=_strings(expected.get("symbols", [])),
        expected_citations=_strings(expected.get("citations", [])),
        minimums=tuple(sorted(minimums)),
    )


def _evaluate_case(case: _Case) -> JsonObject:
    source: JsonObject = {"line": case.source_line, "path": case.source_path}
    if case.mode == "specification":
        return {
            "category": case.category,
            "diagnostics": [],
            "id": case.id,
            "metrics": {name: None for name in METRIC_NAMES},
            "mode": case.mode,
            "source": source,
            "status": "specification",
        }
    assert case.evaluation is not None
    try:
        metrics = _execute(case.evaluation)
        diagnostics = [
            f"metric_below_minimum:{name}"
            for name, minimum in case.evaluation.minimums
            if metrics[name] is None or cast(float, metrics[name]) < minimum
        ]
    except RepoDiveError as error:
        metrics = {name: None for name in METRIC_NAMES}
        diagnostics = [f"execution_error:{error.code}"]
    except Exception:
        metrics = {name: None for name in METRIC_NAMES}
        diagnostics = ["execution_error:evaluation_failed"]
    return {
        "category": case.category,
        "diagnostics": cast(list[JsonValue], diagnostics),
        "id": case.id,
        "metrics": metrics,
        "mode": case.mode,
        "source": source,
        "status": "failed" if diagnostics else "passed",
    }


def _execute(evaluation: _Evaluation) -> JsonObject:
    source = evaluation.repository.resolve(strict=True)
    if not source.is_dir():
        raise EvaluationConfigError("evaluation repository must be a directory")
    with tempfile.TemporaryDirectory(prefix="repo-dive-eval-") as temporary:
        repository = Path(temporary) / "repository"
        shutil.copytree(
            source,
            repository,
            symlinks=True,
            ignore=shutil.ignore_patterns(".repo-dive"),
        )
        IndexService().build(repository)
        retrieved = search_repository(
            repository,
            evaluation.query,
            max_results=evaluation.max_results,
        )
        symbols = {symbol.id: symbol.qualified_name for symbol in retrieved.symbols}
        ranked_paths = tuple(hit.chunk.path for hit in retrieved.fusion.hits)
        ranked_symbols = tuple(
            symbols[hit.chunk.symbol_id]
            for hit in retrieved.fusion.hits
            if hit.chunk.symbol_id in symbols
        )
        estimated_tokens: int | None = None
        citations: tuple[str, ...] = ()
        if evaluation.operation == "context":
            assert evaluation.token_budget is not None
            bundle = EvidencePacker().pack(
                evaluation.query,
                retrieved.fusion.hits,
                token_budget=evaluation.token_budget,
            )
            estimated_tokens = bundle.estimated_tokens
            citations = tuple(item.hit.chunk.path for item in bundle.items)
    return {
        "budget_compliance": (
            budget_compliance(
                estimated_tokens=estimated_tokens,
                token_budget=cast(int, evaluation.token_budget),
            )
            if estimated_tokens is not None
            else None
        ),
        "citation_coverage": citation_coverage(
            citations, evaluation.expected_citations
        ),
        "mrr": reciprocal_rank(ranked_paths, evaluation.expected_paths),
        "path_hit_rate": hit_rate(ranked_paths, evaluation.expected_paths),
        "recall_at_k": recall_at_k(
            ranked_paths,
            evaluation.expected_paths,
            k=evaluation.max_results,
        ),
        "symbol_hit_rate": hit_rate(ranked_symbols, evaluation.expected_symbols),
    }


def _object(value: object) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("expected object")
    return cast(JsonObject, value)


def _string(value: JsonValue) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("expected non-empty string")
    return value


def _strings(value: JsonValue) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("expected string array")
    return tuple(cast(list[str], value))


def _integer(value: JsonValue) -> int:
    if type(value) is not int:
        raise TypeError("expected integer")
    return value


def _number(value: JsonValue) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("expected number")
    return float(value)


def _markdown(report: JsonObject) -> str:
    summary = cast(JsonObject, report["summary"])
    return (
        "# repo-dive evaluation\n\n"
        f"- Passed: {summary['passed']}\n"
        f"- Failed: {summary['failed']}\n"
        f"- Specification only: {summary['specification']}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run isolated repo-dive RAG evaluations."
    )
    parser.add_argument("path", help="JSONL file or directory of JSONL cases")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        report = run_evaluations(args.path)
    except EvaluationConfigError as error:
        print(str(error), file=sys.stderr)
        return 2
    output = (
        serialize_json_document(report) if args.format == "json" else _markdown(report)
    )
    sys.stdout.write(output)
    summary = cast(JsonObject, report["summary"])
    return 1 if cast(int, summary["failed"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["EvaluationConfigError", "main", "run_evaluations"]
