from __future__ import annotations

import io
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.package_smoke import (
    CLI_SMOKE_ARGUMENTS,
    PackageSmokeError,
    find_distributions,
    validate_sdist,
    validate_wheel,
)

RESOURCE = "repo_dive/indexing/schema.sql"


def _wheel(path: Path, *, include_resource: bool = True) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("repo_dive/__init__.py", "")
        if include_resource:
            archive.writestr(RESOURCE, "PRAGMA user_version = 4;\n")


def _sdist(path: Path, *, include_resource: bool = True) -> None:
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


def test_cli_smoke_covers_version_and_four_command_families() -> None:
    assert CLI_SMOKE_ARGUMENTS == (
        ("--version",),
        ("--help",),
        ("index", "--help"),
        ("search", "--help"),
        ("context", "--help"),
        ("wiki", "--help"),
    )
