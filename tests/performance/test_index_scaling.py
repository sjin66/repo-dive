from __future__ import annotations

import gc
import os
import tracemalloc
from pathlib import Path

import pytest

from repo_dive.indexing.service import IndexBuildResult, IndexService
from repo_dive.parsing.models import ParseResult
from repo_dive.parsing.pipeline import ParsingPipeline
from repo_dive.scanner.models import SourceFile
from repo_dive.scanner.service import READ_CHUNK_SIZE, scan_repository


class RecordingParser:
    """Real parsing pipeline with an observable per-file work counter."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        self._delegate = ParsingPipeline(max_chunk_lines=20)

    def parse(self, source: SourceFile) -> ParseResult:
        self.paths.append(source.record.path)
        return self._delegate.parse(source)


def generate_repository(root: Path, *, file_count: int) -> int:
    root.mkdir()
    total_bytes = 0
    for file_index in range(file_count):
        path = root / "src" / f"module_{file_index:04d}.py"
        path.parent.mkdir(exist_ok=True)
        text = "".join(
            f"def shared_marker_{file_index}_{function_index}(value: int) -> int:\n"
            f"    return value + {file_index + function_index}\n\n"
            for function_index in range(4)
        )
        path.write_text(text, encoding="utf-8")
        total_bytes += len(text.encode("utf-8"))
    return total_bytes


def measured_build(repository: Path) -> tuple[IndexBuildResult, int]:
    gc.collect()
    tracemalloc.start()
    try:
        result = IndexService().build(repository, max_chunk_lines=20)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak_bytes


def test_index_work_and_peak_memory_scale_with_runtime_fixture(
    tmp_path: Path,
) -> None:
    small_repository = tmp_path / "small"
    large_repository = tmp_path / "large"
    small_bytes = generate_repository(small_repository, file_count=12)
    large_bytes = generate_repository(large_repository, file_count=48)

    small, small_peak = measured_build(small_repository)
    large, large_peak = measured_build(large_repository)

    assert 3.9 <= large_bytes / small_bytes <= 4.2
    assert small.rebuilt_files == small.counts.files == 12
    assert large.rebuilt_files == large.counts.files == 48
    assert large.counts.chunks == small.counts.chunks * 4
    assert large.counts.symbols == small.counts.symbols * 4
    assert large_peak <= small_peak * 6


def test_incremental_index_reparses_one_changed_file_not_the_corpus(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    file_count = 64
    generate_repository(repository, file_count=file_count)
    parser = RecordingParser()
    service = IndexService()

    first = service.build(repository, parser=parser, max_chunk_lines=20)
    assert first.rebuilt_files == file_count
    assert len(parser.paths) == file_count
    parser.paths.clear()
    changed = repository / "src/module_0031.py"
    changed.write_text(
        changed.read_text(encoding="utf-8")
        + "def changed_only_here() -> str:\n    return 'changed'\n",
        encoding="utf-8",
    )

    second = service.build(repository, parser=parser, max_chunk_lines=20)

    assert second.rebuilt_files == 1
    assert second.reused_files == file_count - 1
    assert second.rebuilt_files < second.counts.files
    assert parser.paths == ["src/module_0031.py"]


def test_scanner_reads_oversized_files_in_fixed_chunks_without_retaining_them(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source_size = READ_CHUNK_SIZE * 32
    source = repository / "oversized.py"
    source.write_bytes(b"x" * source_size)
    source_identity = (source.stat().st_dev, source.stat().st_ino)
    requested_sizes: list[int] = []
    real_read = os.read

    def recording_read(file_descriptor: int, size: int) -> bytes:
        metadata = os.fstat(file_descriptor)
        if (metadata.st_dev, metadata.st_ino) == source_identity:
            requested_sizes.append(size)
        return real_read(file_descriptor, size)

    monkeypatch.setattr("repo_dive.scanner.service.os.read", recording_read)
    gc.collect()
    tracemalloc.start()
    try:
        inventory = scan_repository(repository, max_file_size=READ_CHUNK_SIZE)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert requested_sizes
    assert set(requested_sizes) == {READ_CHUNK_SIZE}
    assert inventory.files[0].text is None
    assert inventory.files[0].record.size_bytes == source_size
    assert peak_bytes < source_size // 2
