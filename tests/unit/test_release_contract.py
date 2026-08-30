from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts/check_release_contract.py"


def _run_release_check(
    *, ref_type: str | None = None, ref_name: str | None = None, ref: str | None = None
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    for name, value in {
        "GITHUB_REF_TYPE": ref_type,
        "GITHUB_REF_NAME": ref_name,
        "GITHUB_REF": ref,
    }.items():
        if value is None:
            environment.pop(name, None)
        else:
            environment[name] = value
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_release_contract_accepts_local_run_without_github_environment() -> None:
    completed = _run_release_check()

    assert completed.returncode == 0
    assert completed.stdout == "Release contract OK: v0.1.0\n"
    assert completed.stderr == ""


def test_release_contract_ignores_branch_ref_name() -> None:
    completed = _run_release_check(
        ref_type="branch", ref_name="main", ref="refs/heads/main"
    )

    assert completed.returncode == 0
    assert completed.stdout == "Release contract OK: v0.1.0\n"
    assert completed.stderr == ""


def test_release_contract_accepts_matching_tag_ref() -> None:
    completed = _run_release_check(
        ref_type="tag", ref_name="v0.1.0", ref="refs/tags/v0.1.0"
    )

    assert completed.returncode == 0
    assert completed.stdout == "Release contract OK: v0.1.0\n"
    assert completed.stderr == ""


def test_release_contract_rejects_mismatched_tag_ref() -> None:
    completed = _run_release_check(
        ref_type="tag", ref_name="v9.9.9", ref="refs/tags/v9.9.9"
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == (
        "release contract error: tag v9.9.9 does not match package version v0.1.0\n"
    )


def test_release_contract_rejects_missing_tag_name() -> None:
    completed = _run_release_check(ref_type="tag", ref_name="", ref="refs/tags/v0.1.0")

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == (
        "release contract error: GitHub tag reference name is missing\n"
    )


def test_release_contract_rejects_tag_name_that_differs_from_full_ref() -> None:
    completed = _run_release_check(
        ref_type="tag", ref_name="v0.1.0", ref="refs/tags/v9.9.9"
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == (
        "release contract error: GitHub tag reference name and full ref differ\n"
    )


def test_release_contract_rejects_tag_type_with_branch_full_ref() -> None:
    completed = _run_release_check(
        ref_type="tag", ref_name="v0.1.0", ref="refs/heads/main"
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == (
        "release contract error: GitHub tag reference is malformed\n"
    )


def test_release_contract_uses_full_tag_ref_when_ref_type_is_unavailable() -> None:
    completed = _run_release_check(ref_type="", ref_name="", ref="refs/tags/v9.9.9")

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == (
        "release contract error: tag v9.9.9 does not match package version v0.1.0\n"
    )


def test_release_contract_rejects_empty_full_tag_ref() -> None:
    completed = _run_release_check(ref_type="", ref_name="", ref="refs/tags/")

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == (
        "release contract error: GitHub tag reference name is missing\n"
    )
