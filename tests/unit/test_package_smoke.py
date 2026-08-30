from __future__ import annotations

import io
import os
import stat
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.archive_bundle import archive_bundle
from scripts.bundle_smoke import extract_archive
from scripts.package_smoke import (
    CLI_SMOKE_ARGUMENTS,
    PackageSmokeError,
    find_distributions,
    validate_sdist,
    validate_wheel,
)

RESOURCE = "repo_dive/indexing/schema.sql"
SKILL_RESOURCE = "repo_dive/_skills/wiki/SKILL.md"
SKILL_REFERENCE = "repo_dive/_skills/wiki/references/workflow-contract.md"


def _wheel(
    path: Path, *, include_resource: bool = True, include_skill: bool = True
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("repo_dive/__init__.py", "")
        if include_resource:
            archive.writestr(RESOURCE, "PRAGMA user_version = 4;\n")
        if include_skill:
            archive.writestr(SKILL_RESOURCE, "---\nname: wiki\n---\n")
            archive.writestr(SKILL_REFERENCE, "# Workflow Contract\n")
            archive.writestr("repo_dive/_skills/wiki/references/release.json", "{}")
            archive.writestr("repo_dive/_skills/wiki/scripts/repo-dive", "#!/bin/sh\n")
            archive.writestr("repo_dive/_skills/wiki/scripts/repo-dive.ps1", "")


def _sdist(
    path: Path, *, include_resource: bool = True, include_skill: bool = True
) -> None:
    with tarfile.open(path, "w:gz") as archive:
        pyproject = b"[project]\nname = 'repo-dive'\n"
        info = tarfile.TarInfo("repo_dive-0.1.0/pyproject.toml")
        info.size = len(pyproject)
        archive.addfile(info, io.BytesIO(pyproject))
        if include_resource:
            schema = b"PRAGMA user_version = 4;\n"
            info = tarfile.TarInfo(f"repo_dive-0.1.0/src/{RESOURCE}")
            info.size = len(schema)
            archive.addfile(info, io.BytesIO(schema))
        if include_skill:
            skill = b"---\nname: wiki\n---\n"
            info = tarfile.TarInfo("repo_dive-0.1.0/skills/wiki/SKILL.md")
            info.size = len(skill)
            archive.addfile(info, io.BytesIO(skill))
            reference = b"# Workflow Contract\n"
            info = tarfile.TarInfo(
                "repo_dive-0.1.0/skills/wiki/references/workflow-contract.md"
            )
            info.size = len(reference)
            archive.addfile(info, io.BytesIO(reference))
            for name, body in (
                ("references/release.json", b"{}"),
                ("scripts/repo-dive", b"#!/bin/sh\n"),
                ("scripts/repo-dive.ps1", b""),
            ):
                info = tarfile.TarInfo(f"repo_dive-0.1.0/skills/wiki/{name}")
                info.size = len(body)
                archive.addfile(info, io.BytesIO(body))


def test_distribution_discovery_requires_one_wheel_and_sdist(tmp_path: Path) -> None:
    wheel = tmp_path / "repo_dive-0.1.0-py3-none-any.whl"
    sdist = tmp_path / "repo_dive-0.1.0.tar.gz"
    _wheel(wheel)
    _sdist(sdist)

    assert find_distributions(tmp_path) == (wheel, sdist)


def test_distribution_discovery_rejects_ambiguous_artifacts(tmp_path: Path) -> None:
    _wheel(tmp_path / "repo_dive-0.1.0-py3-none-any.whl")
    _wheel(tmp_path / "repo_dive-0.2.0-py3-none-any.whl")
    _sdist(tmp_path / "repo_dive-0.1.0.tar.gz")

    with pytest.raises(PackageSmokeError, match="exactly one wheel"):
        find_distributions(tmp_path)


def test_wheel_and_sdist_include_runtime_sql_schema(tmp_path: Path) -> None:
    wheel = tmp_path / "repo_dive-0.1.0-py3-none-any.whl"
    sdist = tmp_path / "repo_dive-0.1.0.tar.gz"
    _wheel(wheel)
    _sdist(sdist)

    validate_wheel(wheel)
    validate_sdist(sdist)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_distribution_validation_rejects_missing_sql_schema(
    tmp_path: Path,
    kind: str,
) -> None:
    validate: Callable[[Path], None]
    if kind == "wheel":
        artifact = tmp_path / "repo_dive-0.1.0-py3-none-any.whl"
        _wheel(artifact, include_resource=False)
        validate = validate_wheel
    else:
        artifact = tmp_path / "repo_dive-0.1.0.tar.gz"
        _sdist(artifact, include_resource=False)
        validate = validate_sdist

    with pytest.raises(PackageSmokeError, match="schema.sql"):
        validate(artifact)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_distribution_validation_rejects_missing_bundled_skill(
    tmp_path: Path, kind: str
) -> None:
    validate: Callable[[Path], None]
    if kind == "wheel":
        artifact = tmp_path / "repo_dive-0.1.0-py3-none-any.whl"
        _wheel(artifact, include_skill=False)
        validate = validate_wheel
    else:
        artifact = tmp_path / "repo_dive-0.1.0.tar.gz"
        _sdist(artifact, include_skill=False)
        validate = validate_sdist

    with pytest.raises(PackageSmokeError, match="skills/wiki/SKILL.md"):
        validate(artifact)


def test_cli_smoke_covers_version_and_four_command_families() -> None:
    assert CLI_SMOKE_ARGUMENTS == (
        ("--version",),
        ("--help",),
        ("init", "--help"),
        ("index", "--help"),
        ("search", "--help"),
        ("context", "--help"),
        ("wiki", "--help"),
    )


@pytest.mark.parametrize(
    ("target", "suffix"),
    [("darwin-arm64", ".tar.gz"), ("windows-x64", ".zip")],
)
def test_native_bundle_archive_has_one_safe_top_level_directory(
    tmp_path: Path, target: str, suffix: str
) -> None:
    bundle = tmp_path / "repo-dive"
    bundle.mkdir()
    executable = bundle / ("repo-dive.exe" if target == "windows-x64" else "repo-dive")
    executable.write_bytes(b"executable")
    (bundle / "_internal").mkdir()
    (bundle / "_internal/runtime.dat").write_bytes(b"runtime")
    output = tmp_path / f"bundle{suffix}"

    archive_bundle(bundle, output, target)

    if target == "windows-x64":
        with zipfile.ZipFile(output) as archive:
            zip_entries = archive.infolist()
            names = [entry.filename for entry in zip_entries]
            assert all(stat.S_ISREG(entry.external_attr >> 16) for entry in zip_entries)
    else:
        with tarfile.open(output) as archive:
            tar_entries = archive.getmembers()
            names = [entry.name for entry in tar_entries]
            assert all(entry.isreg() for entry in tar_entries)
    assert names
    assert all(name == "repo-dive" or name.startswith("repo-dive/") for name in names)
    assert not any(".." in Path(name).parts for name in names)


@pytest.mark.skipif(os.name == "nt", reason="creating symlinks requires privileges")
@pytest.mark.parametrize(
    ("target", "suffix"),
    [("darwin-arm64", ".tar.gz"), ("windows-x64", ".zip")],
)
def test_native_bundle_archive_flattens_pyinstaller_framework_symlinks(
    tmp_path: Path, target: str, suffix: str
) -> None:
    bundle = tmp_path / "repo-dive"
    internal = bundle / "_internal"
    internal.mkdir(parents=True)
    executable = bundle / ("repo-dive.exe" if target == "windows-x64" else "repo-dive")
    executable.write_bytes(b"executable")
    framework = internal / "Python.framework"
    target_file = framework / "Versions" / "3.12" / "Python"
    target_file.parent.mkdir(parents=True)
    target_file.write_bytes(b"framework executable")
    resources = target_file.parent / "Resources"
    resources.mkdir()
    (resources / "Info.plist").write_bytes(b"framework resources")
    (framework / "Versions" / "Current").symlink_to("3.12", target_is_directory=True)
    (framework / "Python").symlink_to(Path("Versions/Current/Python"))
    (framework / "Resources").symlink_to(
        Path("Versions/Current/Resources"), target_is_directory=True
    )
    (internal / "Python").symlink_to(Path("Python.framework/Versions/3.12/Python"))
    output = tmp_path / f"bundle{suffix}"

    archive_bundle(bundle, output, target)

    flattened_files = {
        "repo-dive/_internal/Python",
        "repo-dive/_internal/Python.framework/Python",
    }
    omitted_directory_aliases = {
        "repo-dive/_internal/Python.framework/Resources",
        "repo-dive/_internal/Python.framework/Versions/Current",
    }
    if target == "windows-x64":
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            for archive_name in flattened_files:
                zip_info = archive.getinfo(archive_name)
                assert stat.S_ISREG(zip_info.external_attr >> 16)
                assert archive.read(zip_info) == b"framework executable"
    else:
        with tarfile.open(output) as archive:
            names = set(archive.getnames())
            for archive_name in flattened_files:
                tar_info = archive.getmember(archive_name)
                assert tar_info.isreg()
                source = archive.extractfile(tar_info)
                assert source is not None
                assert source.read() == b"framework executable"
    assert omitted_directory_aliases.isdisjoint(names)


@pytest.mark.skipif(os.name == "nt", reason="creating symlinks requires privileges")
@pytest.mark.parametrize(
    ("target", "suffix"),
    [("darwin-arm64", ".tar.gz"), ("windows-x64", ".zip")],
)
@pytest.mark.parametrize("external_is_directory", [False, True])
def test_native_bundle_archive_rejects_symlinks_outside_bundle(
    tmp_path: Path, target: str, suffix: str, external_is_directory: bool
) -> None:
    bundle = tmp_path / "repo-dive"
    internal = bundle / "_internal"
    internal.mkdir(parents=True)
    executable = bundle / ("repo-dive.exe" if target == "windows-x64" else "repo-dive")
    executable.write_bytes(b"executable")
    external = tmp_path / "external-runtime"
    if external_is_directory:
        external.mkdir()
    else:
        external.write_bytes(b"untrusted")
    (internal / "Python").symlink_to(
        external, target_is_directory=external_is_directory
    )
    output = tmp_path / f"bundle{suffix}"

    with pytest.raises(ValueError, match="symlink target escapes bundle"):
        archive_bundle(bundle, output, target)

    assert not output.exists()


def test_native_bundle_smoke_rejects_archive_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "malicious.tar.gz"
    body = b"escape"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("repo-dive/../../escape")
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))

    with pytest.raises(RuntimeError, match="unsafe archive entry"):
        extract_archive(archive_path, tmp_path / "extract")

    assert not (tmp_path / "escape").exists()
