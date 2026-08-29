from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_init_json_installs_selected_agents_and_reports_unique_destinations(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "repo_dive",
            "init",
            str(tmp_path),
            "--agent",
            "claude-code",
            "--agent",
            "codex",
            "--agent",
            "opencode",
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    document = json.loads(completed.stdout)
    assert document["command"] == "init"
    assert document["repository"] == str(tmp_path.resolve())
    assert document["result"]["agents"] == ["claude-code", "codex", "opencode"]
    assert document["result"]["destinations"] == [
        {
            "agents": ["claude-code"],
            "path": ".claude/skills/wiki",
            "status": "installed",
        },
        {
            "agents": ["codex", "opencode"],
            "path": ".agents/skills/wiki",
            "status": "installed",
        },
    ]


def test_init_json_without_agent_fails_without_reading_stdin(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "repo_dive",
            "init",
            str(tmp_path),
            "--format",
            "json",
        ],
        input="1\ny\n",
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout)["error"]["code"] == "agent_required"
    assert not (tmp_path / ".claude").exists()


def test_init_rejects_invalid_agent_value(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "repo_dive",
            "init",
            str(tmp_path),
            "--agent",
            "other",
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout)["error"]["code"] == "invalid_invocation"
    assert not (tmp_path / ".agents").exists()
