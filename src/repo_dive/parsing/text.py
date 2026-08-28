"""Deterministic fallback parsing for Markdown and plain text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from repo_dive.parsing.models import Chunk, ParseResult, create_chunk
from repo_dive.scanner.models import FileRecord

_MARKDOWN_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+|$)")


@dataclass(frozen=True, slots=True)
class TextParser:
    """Split decoded text while preserving exact source line ranges."""

    window_lines: int = 80
    overlap_lines: int = 10

    def __post_init__(self) -> None:
        if self.window_lines <= 0:
            raise ValueError("window_lines must be greater than zero")
        if not 0 <= self.overlap_lines < self.window_lines:
            raise ValueError(
                "overlap_lines must be non-negative and smaller than window_lines"
            )

    def parse(self, file: FileRecord, text: str) -> ParseResult:
        """Parse one file without accessing the filesystem or process state."""
        lines = text.splitlines(keepends=True)
        if not lines or not text.strip():
            return ParseResult()

        if file.language == "markdown":
            ranges = _markdown_ranges(lines)
        else:
            ranges = _window_ranges(
                lines,
                window_lines=self.window_lines,
                overlap_lines=self.overlap_lines,
            )
        chunks = tuple(
            _chunk_for_range(file.path, lines, start, end) for start, end in ranges
        )
        return ParseResult(chunks=chunks)


def _markdown_ranges(lines: list[str]) -> tuple[tuple[int, int], ...]:
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            if start is not None:
                ranges.append((start, line_number - 1))
                start = None
        elif _MARKDOWN_HEADING.match(line):
            if start is not None:
                ranges.append((start, line_number - 1))
            start = line_number
        elif start is None:
            start = line_number
    if start is not None:
        ranges.append((start, len(lines)))
    return tuple(ranges)


def _window_ranges(
    lines: list[str], *, window_lines: int, overlap_lines: int
) -> tuple[tuple[int, int], ...]:
    ranges: list[tuple[int, int]] = []
    step = window_lines - overlap_lines
    start_index = 0
    while start_index < len(lines):
        end_index = min(start_index + window_lines, len(lines))
        if "".join(lines[start_index:end_index]).strip():
            ranges.append((start_index + 1, end_index))
        if end_index == len(lines):
            break
        start_index += step
    return tuple(ranges)


def _chunk_for_range(
    path: str, lines: list[str], start_line: int, end_line: int
) -> Chunk:
    return create_chunk(
        path=path,
        start_line=start_line,
        end_line=end_line,
        text="".join(lines[start_line - 1 : end_line]),
    )
