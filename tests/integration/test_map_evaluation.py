from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path


def test_knowledge_map_evaluation_cases_are_executable_and_separate_metrics() -> None:
    path = Path("evals/cases/knowledge_map.jsonl")
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    required = {
        "citation_validity",
        "referential_integrity",
        "evidence_freshness",
        "deterministic_reproducibility",
        "semantic_usefulness",
    }

    assert cases
    assert all(set(case["evaluation_dimensions"]) == required for case in cases)
    assert all(
        case["evaluation_dimensions"]["semantic_usefulness"]
        == "manual_not_inferred_from_citations"
        for case in cases
    )
    assert "grounding precision" not in path.read_text(encoding="utf-8").lower()

    for command in sorted({case["command"] for case in cases}):
        completed = subprocess.run(
            shlex.split(command), check=False, capture_output=True, text=True
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
