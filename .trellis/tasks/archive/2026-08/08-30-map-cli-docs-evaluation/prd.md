# Map CLI, Documentation, And Evaluation

## Goal

Expose the completed deterministic and optional semantic Knowledge Map services through one stable `repo-dive map` command family, then prove error, concurrency, security, recovery, performance, evaluation, compatibility, and matched bilingual documentation contracts.

## Dependencies

- Both `08-30-deterministic-knowledge-map` and `08-30-map-evidence-enrichment` must complete before this child starts.
- This is the final implementation child and owns KM-R10/KM-R11 plus public integration of all prior requirements.

## Requirements

### CD-R1 Canonical Command Family

- Expose only `map build`, `map show`, `map evidence`, `map enrich`, `map reset`, and `map validate` with the exact parent flags.
- Do not expose `graph`, `map status`, `init`, `unit`, Wiki topics, or alternate package/artifact names.
- Command adapters own arguments/formatting/service calls only; domain behavior stays in `repo_dive.knowledge_map`.

### CD-R2 Process Contract

- Every command is non-interactive and supports `--format json`.
- JSON mode emits exactly one versioned document to stdout, safe diagnostics to stderr, and no ANSI.
- Repository presentation paths do not expose unnecessary host absolute paths.
- `map show` always requires `--max-results`; `map evidence` requires `--token-budget`; `map build` requires both top-level budgets and strict `--budget-file`.

### CD-R3 Error And Recovery Matrix

- Implement and process-test every parent design error row, exit code, no-write behavior, `retry_mode`, and `recovery_action`.
- Every map error carries parent-defined closed `retry_mode` and `recovery_action` values in existing `error.details`, and overlapping failures obey the parent precedence order.
- Required Evidence that cannot fit token budget is exit `3`; malformed enrichment JSON/schema is exit `2`; stale/unknown repository data and actual repository budget overflow are exit `3`; internal/write failure is exit `4`.
- Lock timeout/revision conflict/index replacement are stable repository-state errors and never silently retry/merge inside the command.

### CD-R4 Security, Recovery, Performance, Compatibility

- Reject path traversal, absolute artifact/input escape, oversized JSON/budget docs, invalid UTF-8, duplicate JSON keys where strict parsing requires, and source-content diagnostic leakage.
- Prove last-valid artifact preservation for every writer failure and read-only behavior for show/validate.
- Verify bounded complexity and result counts without hardware-specific fixed latency promises.
- Existing index/search/context/retrieval/Wiki observable contracts remain green and Wiki never consumes Knowledge Map.

### CD-R5 Evaluation

- Add executable fixtures for linear Python CLI flow, repeated relationship occurrences, cyclic modules, no entrypoint, mixed-language sparse coverage, budget truncation/failure, deterministic no-op rebuild, semantic freshness, and concurrent writers.
- Report citation validity, referential integrity, Evidence freshness, deterministic reproducibility, and semantic usefulness/manual fixture judgment separately.
- Do not label citation presence as semantic grounding precision or truth.
- Every heuristic maps to a fixture and expected structural behavior.

### CD-R6 Matched Documentation

- After executable behavior exists, update matched English/Chinese architecture and CLI contracts and add matched Knowledge Map workflow pages.
- Exact commands, fields, budgets, error/recovery table, lock/revision semantics, semantic validation limits, and no-Wiki boundary match executable help/tests.
- Agent instructions may describe the map as optional but must retain the current Wiki workflow unchanged.
- Documentation never claims unshipped behavior.

### CD-R7 Release Verification

- Run shared Make targets from a freshly prepared clean snapshot and repository-owned tooling checks.
- Inspect exact staged paths; unrelated dirty files and independent `docs/superpowers` proposals are excluded.

## Acceptance Criteria

- **CD-AC1:** `repo-dive map --help` exposes exactly the approved six subcommands/flags and no graph/status/Wiki-topic alias.
- **CD-AC2:** Every success/error JSON path is exactly one parseable document with correct exit/stdout/stderr/ANSI behavior.
- **CD-AC3:** Every checked command/error pair in the parent applicability matrix has an independent process-level test asserting code, exit, no-write, retry classification, and recovery detail.
- **CD-AC4:** Deterministic-only and enriched workflows pass end to end, including reset and concurrent conflict recovery.
- **CD-AC5:** Security/recovery/performance tests prove confinement, bounded work, no lost updates, no diagnostic source leakage, and last-valid preservation.
- **CD-AC6:** Evaluation dimensions are separate and all deterministic heuristics have executable expected cases.
- **CD-AC7:** Existing index/retrieval/context/Wiki suites remain compatible with map artifacts present and absent.
- **CD-AC8:** English/Chinese architecture, CLI, and workflow pairs have equivalent headings/constants/examples/error tables.
- **CD-AC9:** Fresh `make setup`, `make check`, `make test-unit`, `make test-all`, `git diff --check`, and clean-snapshot tooling validation pass.

## Out Of Scope

- New domain algorithms, alternate lock/store/model ownership, Wiki integration, plugins/skills, deployment, dashboard, Markdown as public authority, or independent proposal edits.

## Open Questions

None.
