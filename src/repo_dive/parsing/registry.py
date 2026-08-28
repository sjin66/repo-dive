"""Language-to-parser adapter registry."""

from __future__ import annotations

from repo_dive.parsing.models import ParserAdapter
from repo_dive.parsing.python_ast import PythonAstParser
from repo_dive.parsing.text import TextParser
from repo_dive.parsing.tree_sitter import TreeSitterParser
from repo_dive.scanner.models import FileRecord
from repo_dive.scanner.service import detect_language

_TREE_SITTER_LANGUAGES = {"javascript", "jsx", "tsx", "typescript"}


class ParserRegistry:
    """Select parser adapters without loading optional grammars eagerly."""

    def __init__(self, *, fallback: TextParser | None = None) -> None:
        self._fallback = fallback or TextParser()
        self._python = PythonAstParser(fallback=self._fallback)
        self._tree_sitter = {
            language: TreeSitterParser(language, fallback=self._fallback)
            for language in _TREE_SITTER_LANGUAGES
        }

    def parser_for(self, file: FileRecord) -> ParserAdapter:
        """Return the deterministic adapter selected by detected language."""
        language = (
            detect_language(file.path) if file.language == "unknown" else file.language
        )
        if language == "python":
            return self._python
        return self._tree_sitter.get(language, self._fallback)
