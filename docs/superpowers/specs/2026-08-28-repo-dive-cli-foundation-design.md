# Repo Dive CLI Foundation Design

## Status

Approved for implementation on 2026-08-28.

## Objective

Create a new, independent, pure-Python project named `repo-dive`. Its first delivery establishes the cross-agent harness, bilingual engineering documentation, CI contract, test layout, and an importable CLI shell. Repository scanning, parsing, indexing, retrieval, and wiki generation are deliberately deferred to later deliveries.

## Product Boundary

`repo-dive` is an agent-friendly local CLI intended to be invoked directly by GitHub Copilot or another coding agent. The CLI performs deterministic repository operations and returns machine-readable evidence. The calling agent remains responsible for language-model reasoning and prose generation.

The CLI must not silently invoke a generative model. A future explicit provider adapter may be added as an optional subsystem, but it is outside this foundation.

## Design Philosophy

The project follows seven design principles:

1. **Deterministic core, probabilistic edge.** Repository traversal, parsing, indexing, retrieval, budgeting, persistence, and assembly belong to the CLI. Interpretation and prose generation belong to the calling agent.
2. **Evidence before narrative.** Every generated claim should be traceable to repository-relative paths, symbols, and one-based line ranges. Retrieval results are first-class artifacts rather than hidden prompt fragments.
3. **Explicit staged artifacts.** Structure planning, page context, page content, and final assembly are separate steps with inspectable intermediate state. A failed run can resume without repeating completed work.
4. **Stable contracts over conversational conventions.** Commands expose versioned JSON schemas, defined exit codes, isolated stdout/stderr behavior, and stable on-disk paths so agents can automate the CLI reliably.
5. **Local-first ownership.** Analysis runs against the local repository, and generated knowledge stays with that repository under `.repo-dive/`. Network-backed embeddings or providers must remain explicit and optional.
6. **Replaceable retrieval components.** Parsing, lexical search, vector search, ranking, and context assembly communicate through narrow interfaces so one strategy can evolve without rewriting the workflow.
7. **One harness for humans, agents, and CI.** The same documented commands set up, check, and test the project in every environment.

## Wiki Workflow

The future wiki workflow applies those principles through an evidence-first pipeline:

1. Scan the repository tree and read the README.
2. Produce a wiki structure containing pages and relevant source files.
3. Retrieve source context independently for each page.
4. Let the calling agent generate each page from that evidence.
5. Persist the intermediate structure and page content.
6. Assemble a table of contents, related-page links, and page bodies into one Markdown document.

The target repository owns the generated artifacts. The stable output contract is:

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
