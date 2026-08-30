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

## Calling-Agent Workflow

MCP is not required. GitHub Copilot and other agents should invoke the
non-interactive CLI directly, request JSON, check the process exit code, and
parse stdout only as one complete JSON document.

For ad hoc repository questions:

1. Run `repo-dive index <repository> --format json` when no current index
   exists or source has changed.
2. Run `repo-dive context <repository> <query> --token-budget <tokens>
   --format json`.
3. Generate an answer only from returned Evidence, preserving paths and
   one-based inclusive line ranges.

For a persistent Wiki, use this resumable sequence:

1. `repo-dive index <repository> --format json`
2. `repo-dive wiki classify <repository> --format json`
3. `repo-dive wiki init <repository> --locale en|zh-CN|ja --format json`
4. `repo-dive wiki evidence <repository> --page <page-id> --token-budget
   <tokens> --format json`
5. Use the calling agent's current model to generate page Markdown from the
   returned Evidence. This is the context-to-generate boundary; the CLI does
   not call a model. Do not use generic `context` as a substitute for persisted
   Wiki Evidence.
6. Submit `page.json` with the exact returned `evidence_id` values using
   `repo-dive wiki page <repository> --page <page-id> --input page.json
   --format json`. For pipelines, pass the same JSON through `--input -`.
7. Repeat Evidence collection, generation, and page submission until
   `repo-dive wiki status <repository> --format json` reports every page as
   `generated`.
8. Run `repo-dive wiki validate <repository> --format json` and correct any
   contract violation before publication.
9. Run `repo-dive wiki build <repository> --format json`; consume
   `<repository>/.repo-dive/wiki.md` only after exit code `0`.

In short: `index -> context (wiki evidence) -> generate -> wiki page -> validate -> build`.
On exit code `2`, correct the invocation or JSON input without retrying it
unchanged. On exit code `3`, inspect the stable error code; rebuild the index
for `index_not_found` or `index_stale`, recollect Evidence for
`wiki_evidence_stale`, and otherwise preserve current artifacts. On exit code
`4`, surface the safe diagnostic and keep the last valid index or Wiki output;
never parse stderr as source Evidence.

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
<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->
