"""Create a stable-layout release archive from a PyInstaller onedir bundle."""

from __future__ import annotations

import argparse
import os
import tarfile
import zipfile
from pathlib import Path

TARGETS = {
    "darwin-arm64": "tar.gz",
    "darwin-x64": "tar.gz",
    "windows-x64": "zip",
}


def _archive_source(path: Path, bundle: Path) -> Path | None:
    """Return safe file content for ``path``, omitting directory aliases."""
    if not path.is_symlink():
        return path
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"bundle symlink target is unavailable: {path}") from error
    try:
        resolved.relative_to(bundle.resolve())
    except ValueError as error:
        raise ValueError(f"symlink target escapes bundle: {path}") from error
    if resolved.is_file():
        return resolved
    if resolved.is_dir():
        # PyInstaller's macOS framework contains Current and Resources directory
        # aliases. Their targets are already archived at their canonical paths;
        # omitting the aliases keeps release archives link-free.
        return None
    raise ValueError(f"bundle symlink target is not a file or directory: {path}")


def archive_bundle(bundle: Path, output: Path, target: str) -> None:
    """Archive ``bundle`` beneath one ``repo-dive`` root with normalized metadata."""
    if target not in TARGETS:
        raise ValueError(f"unsupported bundle target: {target}")
    executable = bundle / ("repo-dive.exe" if target == "windows-x64" else "repo-dive")
    if bundle.name != "repo-dive" or not executable.is_file():
        raise ValueError("bundle must be a repo-dive onedir with its executable")
    paths = sorted(
        (path for path in bundle.rglob("*") if path.is_file() or path.is_symlink()),
        key=lambda path: path.as_posix(),
    )
    sources = [
        (path, source)
        for path in paths
        if (source := _archive_source(path, bundle)) is not None
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    if TARGETS[target] == "zip":
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, source in sources:
                name = Path("repo-dive") / path.relative_to(bundle)
                zip_info = zipfile.ZipInfo(name.as_posix(), (1980, 1, 1, 0, 0, 0))
                zip_info.external_attr = (source.stat().st_mode & 0xFFFF) << 16
                archive.writestr(
                    zip_info,
                    source.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                )
        return
    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for path, source in sources:
            archive_name = (Path("repo-dive") / path.relative_to(bundle)).as_posix()
            tar_info = archive.gettarinfo(source, arcname=archive_name)
            tar_info.uid = tar_info.gid = 0
            tar_info.uname = tar_info.gname = ""
            tar_info.mtime = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
            with source.open("rb") as stream:
                archive.addfile(tar_info, stream)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    args = parser.parse_args()
    archive_bundle(args.bundle, args.output, args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
