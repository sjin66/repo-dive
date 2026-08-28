"""Deterministic repository scanning."""

from repo_dive.scanner.candidates import CandidateSet, discover_candidates
from repo_dive.scanner.models import FileRecord, Inventory, SourceFile
from repo_dive.scanner.service import scan_repository

__all__ = [
    "CandidateSet",
    "FileRecord",
    "Inventory",
    "SourceFile",
    "discover_candidates",
    "scan_repository",
]
