"""Language-aware and fallback source parsing."""

from repo_dive.parsing.models import (
    Chunk,
    ParserAdapter,
    ParseResult,
    Relationship,
    Symbol,
)
from repo_dive.parsing.pipeline import ParsingPipeline
from repo_dive.parsing.python_ast import PythonAstParser
from repo_dive.parsing.text import TextParser
from repo_dive.parsing.tree_sitter import TreeSitterParser

__all__ = [
    "Chunk",
    "ParseResult",
    "ParserAdapter",
    "ParsingPipeline",
    "PythonAstParser",
    "Relationship",
    "Symbol",
    "TextParser",
    "TreeSitterParser",
]
