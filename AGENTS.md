# Agent Guide

## Authority

This file is the authoritative repository-wide instruction set. Tool-specific instruction files may reference it but must not duplicate or override it. A nested `AGENTS.md` may add narrower rules for its subtree only when the distinction is necessary.

## Product Boundary

`repo-dive` is a pure-Python, agent-friendly local RAG CLI for collecting grounded evidence from repositories and assembling repository-owned knowledge artifacts. The CLI owns ingestion, indexing, retrieval, ranking, context packaging, and artifact persistence. The calling agent performs interpretation and prose generation. The CLI must never invoke a generative model implicitly.

Treat `tasks/todo.md`, executable help, and tests as the implementation-status authority. Do not present unchecked planned tasks as implemented.

## Design Principles

- Keep the core deterministic and move probabilistic reasoning to the calling agent.
- Return evidence before narrative: repository-relative paths, symbols, and one-based line ranges.
- Treat RAG as an explicit pipeline: parse and chunk, build lexical/structural/optional-vector indexes, retrieve and fuse candidates, apply a context budget, then hand evidence to the caller.
- Persist explicit stage outputs so interrupted workflows can resume.
- Prefer stable, versioned machine contracts over prompt conventions.
- Keep repository data and generated knowledge local by default.
- Hide retrieval implementations behind narrow interfaces.
- Use the same setup and verification entry points for humans, agents, and CI.

## Source Boundaries

- `src/repo_dive/cli.py`: process arguments, stdout/stderr, and exit codes only.
- `scanner`: repository traversal and filtering.
- `parsing`: language adapters and symbol extraction.
- `indexing`: chunk, lexical, vector, and relationship persistence.
- `retrieval`: ranking and result fusion.
- `context`: evidence selection under an explicit budget.
- `wiki`: structure, page state, and Markdown assembly.

Domain modules must not depend on terminal rendering, environment-variable lookup, or a concrete embedding/model provider. Put provider and filesystem details behind explicit adapters.

## CLI Contract

Functional commands must be non-interactive and support `--format json`.

- JSON mode writes exactly one valid result document to `stdout`.
- Progress and diagnostics go to `stderr`.
- JSON mode emits no ANSI control sequences.
- Exit code `0`: success.
- Exit code `2`: invocation or validation error.
- Exit code `3`: repository or input error.
- Exit code `4`: internal operation failure.
- Evidence uses repository-relative POSIX paths and one-based inclusive line numbers.
- Potentially large commands require an explicit token or result budget.

## Repository Artifact Contract

Generated artifacts belong under the analyzed repository's `.repo-dive/` directory:

```text
.repo-dive/
├── wiki.md
├── wiki.json
├── metadata.json
└── index/
```

`wiki.md` is the stable current document. Writes must be atomic. Never modify the analyzed repository's `.gitignore` automatically.

## Development Rules

- Support Python 3.11 and newer.
- Use type annotations for public and internal interfaces.
- Prefer focused modules and immutable data passed between stages.
- Validate repository paths before reading or writing; reject traversal outside the selected root.
- Do not log secrets, full environment dumps, access tokens, or private source contents.
- Keep runtime dependencies minimal and justify each addition in the relevant design document.
- Use `apply_patch` or an equivalently reviewable patch for hand-written file changes.

## Testing and Evaluation

Behavior changes follow red-green-refactor TDD. Tests assert observable behavior rather than implementation text. Add retrieval heuristics only with an evaluation case that demonstrates the intended improvement.

Required entry points:

```bash
make setup
make check
make test-unit
make test-all
```

Before claiming completion, run `make check` and `make test-all` from a freshly prepared environment. CI must call the same Make targets and must not duplicate Ruff, mypy, or pytest commands.

## Documentation

Agent and harness instructions are written in English. User-facing and developer-facing CLI documentation is maintained in matched pairs under `docs/en/` and `docs/zh-CN/`. Update both files in a pair in the same change and preserve equivalent headings and technical contracts.

Implementation plans live in `docs/superpowers/plans/`; approved design specifications live in `docs/superpowers/specs/`.
