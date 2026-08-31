import json
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {"id", "category", "mode", "prompt", "expected_behavior"}
OPTIONAL_FIELDS = {"command", "assertions", "evaluation", "evaluation_dimensions"}


def _load_cases() -> list[dict[str, Any]]:
    case_files = sorted(Path("evals/cases").glob("*.jsonl"))
    assert case_files, "no evaluation case files found"

    cases: list[dict[str, Any]] = []
    for case_file in case_files:
        for line_number, line in enumerate(
            case_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.strip():
                value = json.loads(line)
                assert isinstance(value, dict), (
                    f"{case_file}:{line_number} is not an object"
                )
                cases.append(value)
    return cases


def test_evaluation_cases_follow_the_manifest_contract() -> None:
    cases = _load_cases()
    seen_ids: set[str] = set()

    for case in cases:
        assert case.keys() >= REQUIRED_FIELDS
        assert case.keys() <= REQUIRED_FIELDS | OPTIONAL_FIELDS
        for field in REQUIRED_FIELDS:
            assert isinstance(case[field], str) and case[field]

        case_id = case["id"]
        assert case_id not in seen_ids
        seen_ids.add(case_id)

        assert case["mode"] in {"executable", "specification"}
        if case["mode"] == "executable":
            assert isinstance(case.get("evaluation"), dict)
        else:
            assert "evaluation" not in case

        if "command" in case:
            assert isinstance(case["command"], str) and case["command"]
        if "assertions" in case:
            assert isinstance(case["assertions"], list)
            assert all(isinstance(item, str) and item for item in case["assertions"])
        if "evaluation_dimensions" in case:
            assert isinstance(case["evaluation_dimensions"], dict)
            assert set(case["evaluation_dimensions"]) == {
                "citation_validity",
                "referential_integrity",
                "evidence_freshness",
                "deterministic_reproducibility",
                "semantic_usefulness",
            }
