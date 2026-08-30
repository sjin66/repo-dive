"""Validate marketplace release metadata against package and plugin versions."""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path

EXPECTED_REPOSITORY = "https://github.com/sjin66/repo-dive"
EXPECTED_TARGETS = {
    "darwin-arm64": {
        "archive_type": "tar.gz",
        "executable": "repo-dive",
    },
    "darwin-x64": {
        "archive_type": "tar.gz",
        "executable": "repo-dive",
    },
    "windows-x64": {
        "archive_type": "zip",
        "executable": "repo-dive.exe",
    },
}


def main() -> int:
    root = Path(__file__).parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    release_path = root / "skills/wiki/references/release.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    manifests = [
        "plugin.json",
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        "gemini-extension.json",
    ]
    errors: list[str] = []
    init_path = root / "src/repo_dive/__init__.py"
    init_namespace: dict[str, object] = {}
    exec(init_path.read_text(encoding="utf-8"), init_namespace)
    if init_namespace.get("__version__") != version:
        errors.append("repo_dive.__version__ differs from the package")
    if release.get("version") != version or release.get("tag") != f"v{version}":
        errors.append("release metadata version differs from the package")
    if release.get("schema_version") != "1.0":
        errors.append("release metadata schema version is invalid")
    if release.get("repository") != EXPECTED_REPOSITORY:
        errors.append("release metadata repository is invalid")
    for manifest in manifests:
        data = json.loads((root / manifest).read_text(encoding="utf-8"))
        if data.get("name") != "repo-dive" or data.get("version") != version:
            errors.append(f"{manifest} package identity or version differs")
    targets = release.get("targets")
    if not isinstance(targets, dict) or set(targets) != set(EXPECTED_TARGETS):
        errors.append("release target archive mapping is incomplete or inconsistent")
    else:
        for target, expected in EXPECTED_TARGETS.items():
            item = targets[target]
            suffix = expected["archive_type"]
            if not isinstance(item, dict) or item != {
                "archive": f"repo-dive-v{version}-{target}.{suffix}",
                "archive_type": suffix,
                "top_level": "repo-dive",
                "executable": expected["executable"],
            }:
                errors.append(f"release target metadata is invalid: {target}")
    github_ref = os.environ.get("GITHUB_REF_NAME")
    if github_ref and github_ref != f"v{version}":
        errors.append(f"tag {github_ref} does not match package version v{version}")
    if errors:
        for error in errors:
            print(f"release contract error: {error}", file=sys.stderr)
        return 1
    print(f"Release contract OK: v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
