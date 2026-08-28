from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

import repo_dive.scanner.service as scanner_service
from repo_dive.errors import InvocationError
from repo_dive.scanner.candidates import CandidateSet
from repo_dive.scanner.models import ReadStatus, SkipReason
from repo_dive.scanner.service import scan_repository


def write_bytes(repository: Path, relative_path: str, content: bytes) -> Path:
    target = repository / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def test_scan_builds_readable_file_record_and_text(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    content = b"print('hello')\n"
    write_bytes(repository, "src/main.py", content)

    inventory = scan_repository(repository)

    assert inventory.mode == "filesystem"
    assert len(inventory.files) == 1
    source_file = inventory.files[0]
    assert source_file.record.path == "src/main.py"
    assert source_file.record.size_bytes == len(content)
    assert source_file.record.language == "python"
    assert source_file.record.content_hash == hashlib.sha256(content).hexdigest()
    assert source_file.record.encoding == "utf-8"
    assert source_file.record.status is ReadStatus.READ
    assert source_file.record.skip_reason is None
    assert source_file.text == "print('hello')\n"


def test_scan_reports_structured_skip_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    contents = {
        "binary.dat": b"\x00x",
        "invalid.txt": b"\xff",
        "oversized.txt": b"12345",
        "unreadable.py": b"secret = True\n",
    }
    paths = {
        name: write_bytes(repository, name, content)
        for name, content in contents.items()
    }
    original_open = os.open

    def controlled_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes], flags: int
    ) -> int:
        if os.fsdecode(path) == os.fspath(paths["unreadable.py"]):
            raise PermissionError("simulated unreadable file")
        return original_open(path, flags)

    monkeypatch.setattr(os, "open", controlled_open)

    inventory = scan_repository(repository, max_file_size=4)

    files = {source.record.path: source for source in inventory.files}
    assert files["binary.dat"].record.skip_reason is SkipReason.BINARY
    assert files["invalid.txt"].record.skip_reason is SkipReason.INVALID_ENCODING
    assert files["oversized.txt"].record.skip_reason is SkipReason.TOO_LARGE
    assert files["unreadable.py"].record.skip_reason is SkipReason.UNREADABLE
    assert files["unreadable.py"].record.content_hash is None
    assert all(source.record.status is ReadStatus.SKIPPED for source in files.values())
    assert all(source.text is None for source in files.values())
    for path in ("binary.dat", "invalid.txt", "oversized.txt"):
        assert (
            files[path].record.content_hash
            == hashlib.sha256(contents[path]).hexdigest()
        )


@pytest.mark.parametrize(
    ("relative_path", "expected_language"),
    [
        ("pyproject.toml", "toml"),
        ("README.md", "markdown"),
        ("src/app.tsx", "tsx"),
        ("src/main.go", "go"),
        ("Dockerfile", "dockerfile"),
        ("unknown.custom", "unknown"),
    ],
)
def test_scan_detects_language_from_path(
    tmp_path: Path, relative_path: str, expected_language: str
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    write_bytes(repository, relative_path, b"source\n")

    inventory = scan_repository(repository)

    assert inventory.files[0].record.language == expected_language


def test_scan_is_deterministic_and_content_sensitive(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    write_bytes(repository, "z.py", b"z = 1\n")
    changed = write_bytes(repository, "a.py", b"a = 1\n")

    first = scan_repository(repository)
    second = scan_repository(repository)
    changed.write_bytes(b"a = 2\n")
    third = scan_repository(repository)

    assert first == second
    assert tuple(source.record.path for source in first.files) == ("a.py", "z.py")
    assert first.repository_fingerprint == second.repository_fingerprint
    assert first.repository_fingerprint != third.repository_fingerprint


def test_scan_rejects_non_positive_file_size_limit(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    with pytest.raises(InvocationError) as exc_info:
        scan_repository(repository, max_file_size=0)

    assert exc_info.value.code == "invalid_max_file_size"


def test_scan_rejects_symlink_swap_without_no_follow_support(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = write_bytes(tmp_path, "outside/secret.py", b"SECRET = True\n")
    (repository / "source.py").symlink_to(outside)

    def swapped_candidates(
        repository_path: str | Path,
        *,
        include: tuple[str, ...] = (),
        exclude: tuple[str, ...] = (),
    ) -> CandidateSet:
        return CandidateSet(mode="filesystem", paths=("source.py",))

    monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)
    monkeypatch.setattr(scanner_service, "discover_candidates", swapped_candidates)

    inventory = scan_repository(repository)

    source = inventory.files[0]
    assert source.record.skip_reason is SkipReason.UNREADABLE
    assert source.text is None
