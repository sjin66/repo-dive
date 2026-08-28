# Architecture

## System Boundary

`repo-dive` is a local process invoked by a human or coding agent. It reads an explicitly selected repository, writes only to that repository's `.repo-dive/` directory, and emits structured command results. The caller owns language-model reasoning.

```text
Calling agent
    | argv / stdin
    v
CLI boundary
    |
    +--> scan and parse repository
    +--> build and query indexes
    +--> assemble bounded evidence
    +--> persist wiki state
    |
    v
stdout JSON/Markdown + .repo-dive artifacts
```

The CLI does not inherit the caller's model session and must not hide a second model call behind a deterministic command.

## Design Principles

### Deterministic core, probabilistic edge

Operations that can be reproduced from repository bytes belong in the CLI. Interpretation, prioritization of ambiguous concepts, and prose generation belong to the caller. This split makes failures observable and avoids nested agent loops.

### Evidence before narrative

Retrieval returns source text with repository-relative paths, symbols, and one-based line ranges. A wiki page is assembled only after its evidence set is recorded. Generated prose is therefore reviewable against the inputs that supported it.

### Explicit and resumable stages

Scanning, parsing, indexing, retrieval, page persistence, and document assembly have independent artifacts and state transitions. Re-running a completed stage is idempotent; an interrupted workflow resumes from durable state.

### Stable contracts

Agents integrate through versioned JSON schemas, documented exit codes, strict stdout/stderr separation, and stable filesystem paths. Prompt wording is not an API.

### Local-first ownership

Source code and generated artifacts remain local by default. A future network-backed embedder must be selected explicitly and disclose what data it transmits. The analyzed repository owns `.repo-dive/` and decides whether to ignore or commit it.

### Replaceable components

Lexical retrieval, vector retrieval, ranking, syntax parsers, and persistence adapters meet at typed domain models. The default implementation can evolve without changing command schemas or wiki state.

### One verification harness

Humans, coding agents, and CI use the same Make targets. A command that passes only in a bespoke CI script is not a supported workflow.

## Planned Package Boundaries

```text
src/repo_dive/
├── cli.py
├── scanner/
├── parsing/
├── indexing/
├── retrieval/
├── context/
└── wiki/
```

- `cli.py` translates process input into application requests and serializes results.
- `scanner` selects files without interpreting language syntax.
- `parsing` extracts language-aware chunks, symbols, and structural relationships.
- `indexing` persists lexical, vector, and relationship representations.
- `retrieval` ranks evidence without formatting a model prompt.
- `context` selects and serializes evidence under an explicit budget.
- `wiki` persists structures/pages and atomically assembles `wiki.md`.

Shared domain types belong next to the behavior that owns them. Avoid a catch-all `utils` or `models` module.

## Local RAG Architecture

RAG (retrieval-augmented generation) is divided across the deterministic CLI and the probabilistic calling agent:

```text
local repository
    -> scan and filter
    -> syntax-aware parse and chunk
    -> structural + BM25 + optional vector indexes
    -> query candidate retrieval
    -> score fusion, deduplication, and relationship expansion
    -> token-budgeted evidence package
    -> calling Copilot model generates a page
    -> repo-dive validates citations and persists the page
```

### Ingestion

The scanner creates a reproducible file inventory. Language adapters then prefer Tree-sitter or a language-native AST to split code at symbol boundaries. A fallback text splitter is allowed for unsupported languages and documentation. Each chunk carries a content fingerprint, repository-relative path, line range, symbol identity when known, and structural relationships.

### Indexes

The default RAG design uses three complementary evidence channels:

- **Structural index:** files, symbols, imports, calls, inheritance, and containment relationships.
- **BM25 lexical index:** exact identifiers, error strings, configuration keys, and domain terminology.
- **Optional vector index:** semantic similarity when the user explicitly configures a local or remote embedding provider.

BM25 and structural retrieval must work without credentials or a network connection. Vector retrieval enhances recall but cannot be required for basic repository understanding.

### Retrieval and ranking

A query may come directly from the caller or from a persisted wiki-page description. Each enabled channel returns candidates with its own score. The retrieval layer fuses candidates through a documented, replaceable strategy, removes duplicate/overlapping chunks, and may expand high-confidence symbol relationships. It must preserve component scores so results remain explainable.

### Context assembly

The context layer selects diverse evidence under an explicit token budget. It reserves space for stable metadata, prioritizes primary implementation over duplicated/generated content, and reports excluded or truncated evidence. Its output is a versioned evidence package, not an opaque prompt string.

### Generation boundary

The evidence package is returned to the calling Copilot session. Copilot uses its current model and conversation context to generate the requested page, then sends the page back to the CLI for validation and persistence. This is still RAG: retrieval augments generation, but retrieval and generation execute in different processes. The CLI must not create an implicit nested model session.

### Grounding and evaluation

Generated claims cite evidence paths and line ranges. Retrieval changes require evaluation cases for recall, ranking, budget use, and citation coverage. Prose style is not a retrieval-quality metric.

## Dependency Direction

Domain and application behavior depend on protocols, not concrete clients. Filesystem, embedding, vector-store, tokenizer, and terminal implementations sit at the edge and are injected explicitly. Environment variables are resolved once at the CLI/configuration boundary.

## Data and State

The analyzed repository is the identity boundary. Metadata includes a normalized repository root, source commit when available, schema version, index version, output language, and timestamps. Index validity is derived from repository fingerprints rather than directory names alone.

Wiki writes use a temporary sibling file followed by an atomic replace. A failed assembly must leave the previous `wiki.md` readable.

## Security Boundary

All requested paths are resolved and checked against the selected repository root. Symlink and traversal escapes are rejected. Diagnostics redact credentials and do not dump source content. Network access is off unless an explicit command/provider requests it.
