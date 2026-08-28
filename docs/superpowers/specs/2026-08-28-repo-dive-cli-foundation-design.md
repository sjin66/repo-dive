# Repo Dive CLI Foundation Design

## Status

Approved for implementation on 2026-08-28.

## Objective

Create a new, independent, pure-Python project named `repo-dive`. Its first delivery establishes the cross-agent harness, bilingual engineering documentation, CI contract, test layout, and an importable CLI shell. Repository scanning, parsing, indexing, retrieval, and wiki generation are deliberately deferred to later deliveries.

## Product Boundary

`repo-dive` is an agent-friendly local CLI intended to be invoked directly by GitHub Copilot or another coding agent. The CLI performs deterministic repository operations and returns machine-readable evidence. The calling agent remains responsible for language-model reasoning and prose generation.

The CLI must not silently invoke a generative model. A future explicit provider adapter may be added as an optional subsystem, but it is outside this foundation.

## DeepWiki-Compatible Wiki Workflow

The future wiki workflow preserves the useful orchestration shape of deepwiki-open:

1. Scan the repository tree and read the README.
2. Produce a wiki structure containing pages and relevant source files.
3. Retrieve source context independently for each page.
4. Let the calling agent generate each page from that evidence.
5. Persist the intermediate structure and page content.
6. Assemble a table of contents, related-page links, and page bodies into one Markdown document.

Unlike deepwiki-open, the target repository owns the generated artifacts. The stable output contract is:

```text
<repository>/.repo-dive/
├── wiki.md
├── wiki.json
├── metadata.json
└── index/
```

`wiki.md` is always the current assembled document. `wiki.json` is the structured intermediate representation. `metadata.json` records the source commit, output language, generation timestamp, and schema/index versions. `index/` contains implementation-private retrieval data. History snapshots are not part of the first version.

## Planned Runtime Architecture

Future functionality will be split into focused Python packages:

```text
repo_dive
├── cli                 command parsing and process-level I/O
├── scanner             repository traversal and filtering
├── parsing             Tree-sitter/AST adapters and symbol extraction
├── indexing            chunk, lexical, vector, and relationship indexes
├── retrieval           BM25/vector fusion and evidence ranking
├── context             token-budgeted context assembly
└── wiki                structure, page persistence, and Markdown assembly
```

Dependencies flow inward through explicit data models. Domain behavior must not depend on terminal rendering, environment variables, or a specific embedding provider.

## Agent-Friendly Process Contract

All future functional commands must support non-interactive execution. When `--format json` is selected:

- `stdout` contains exactly one valid JSON result document.
- Diagnostics and progress go to `stderr`.
- ANSI escape sequences are disabled.
- Exit code `0` means success, `2` means invocation or validation error, `3` means repository/input error, and `4` means an internal operation failed.
- Results include repository-relative paths and one-based line numbers where applicable.
- Commands accepting large result sets expose an explicit token or result budget.

The foundation implements only `repo-dive --help` and `repo-dive --version`; functional subcommands come later.

## Harness Authority

Root `AGENTS.md` is the single authoritative agent contract. Compatibility files for GitHub Copilot, Claude, and Gemini only reference it and must not restate competing rules.

Agent-facing and harness documentation is written in English. User-facing and developer-facing CLI documentation is maintained in paired English and Simplified Chinese files.

## Verification Contract

The project exposes exactly these shared entry points:

```bash
make setup
make check
make test-unit
make test-all
```

CI invokes the same Make targets rather than duplicating tool commands. Python 3.11 is the minimum supported version. The foundation uses `pytest`, `ruff`, and strict `mypy` checks.

## Test and Evaluation Layout

- `tests/unit/` verifies isolated Python and CLI-shell behavior.
- `tests/integration/` is reserved for repository-level workflows.
- `tests/fixtures/` contains intentionally small repository fixtures.
- `evals/cases/` stores versioned, machine-readable agent/RAG evaluation cases.
- Foundation tests validate that evaluation manifests are syntactically valid and contain required fields.

Later retrieval work must add evidence-grounding evaluations before adding ranking heuristics.

## Foundation Deliverables

The first implementation creates:

- Python packaging and the `repo-dive` console entry point.
- Root agent authority plus compatibility instruction files.
- English and Simplified Chinese README and engineering documentation.
- Make-based local harness and GitHub Actions CI.
- Unit/integration/fixture/evaluation directories and foundation tests.
- No scanner, parser, index, retriever, context builder, or wiki generator implementation.

## Non-Goals

- No web frontend or HTTP API.
- No MCP server.
- No built-in generative-model call.
- No repository cloning in the foundation.
- No Tree-sitter, embedding, FAISS, or BM25 dependency in the foundation.
- No automatic modification of an analyzed repository's `.gitignore`.

