import json
import subprocess
import sys


def test_invalid_json_invocation_keeps_stdout_machine_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "repo_dive", "unknown", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert completed.stdout.endswith("\n")
    assert not completed.stdout.endswith("\n\n")
    assert "\x1b[" not in completed.stdout
    assert "\x1b[" not in completed.stderr
    assert json.loads(completed.stdout) == {
        "schema_version": "1.0",
        "command": "unknown",
        "error": {
            "code": "invalid_invocation",
            "message": "unrecognized arguments: unknown --format json",
        },
    }
    assert "unrecognized arguments" in completed.stderr
