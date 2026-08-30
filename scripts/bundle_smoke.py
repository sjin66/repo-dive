"""Smoke-test an extracted native Repo Dive onedir bundle."""

from __future__ import annotations

import argparse
import json
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path


def run(executable: Path, *args: str) -> str:
    completed = subprocess.run(
        [executable, *args], check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    return completed.stdout


def _safe_parts(name: str) -> tuple[str, ...]:
    normalized = name.replace("\\", "/")
    parts = tuple(part for part in normalized.split("/") if part)
    if normalized.startswith("/") or not parts or ".." in parts:
        raise RuntimeError(f"unsafe archive entry: {name}")
    if parts[0] != "repo-dive":
        raise RuntimeError(f"unexpected archive root: {name}")
    return parts


def extract_archive(archive_path: Path, destination: Path) -> Path:
    """Validate and extract a native release archive for smoke testing."""
    if archive_path.name.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as archive:
            for zip_entry in archive.infolist():
                _safe_parts(zip_entry.filename)
                if (zip_entry.external_attr >> 16) & 0xF000 == 0xA000:
                    raise RuntimeError(f"archive link entry: {zip_entry.filename}")
            archive.extractall(destination)
    else:
        with tarfile.open(archive_path, "r:gz") as archive:
            for tar_entry in archive.getmembers():
                _safe_parts(tar_entry.name)
                if tar_entry.issym() or tar_entry.islnk():
                    raise RuntimeError(f"archive link entry: {tar_entry.name}")
            archive.extractall(destination, filter="data")
    return destination / "repo-dive"


def smoke_bundle(bundle: Path, target: str) -> None:
    executable_name = "repo-dive.exe" if target == "windows-x64" else "repo-dive"
    executable = bundle / executable_name
    run(executable, "--version")
    run(executable, "--help")
    with tempfile.TemporaryDirectory(prefix="repo-dive-bundle-smoke-") as directory:
        repository = Path(directory) / "repository"
        repository.mkdir()
        (repository / "app.js").write_text(
            "export function greet(name) { return `hi ${name}`; }\n",
            encoding="utf-8",
        )
        (repository / "types.ts").write_text(
            "export interface User { name: string }\n", encoding="utf-8"
        )
        output = run(executable, "index", str(repository), "--format", "json")
        result = json.loads(output)
        warnings = result.get("warnings", [])
        if any("tree_sitter_unavailable" in str(item) for item in warnings):
            raise RuntimeError("native Tree-sitter grammar was unavailable")
        if result["result"]["indexed_files"] != 2 or result["result"]["symbols"] < 2:
            raise RuntimeError(
                "JavaScript/TypeScript structural smoke did not produce symbols"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="repo-dive-archive-smoke-") as directory:
        bundle = extract_archive(args.archive, Path(directory))
        smoke_bundle(bundle, args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
