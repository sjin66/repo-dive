# Knowledge Map Final Integration Corrections Implementation Plan

## I0: Sanitize Real Missing-Index Map Errors

- Add a failing focused regression showing `index_not_found` retains an absolute path
  before Map error adaptation and loses only that field afterward.
- Add `index_not_found` to the existing Map-only path-removal set in
  `src/repo_dive/cli.py`.
- Assert stable code/message/exit/recovery values and verify a non-Map invocation still
  preserves its established details.

**Primary files:** `src/repo_dive/cli.py`, `tests/unit/test_cli_errors.py`, and the six
real process cases in `tests/integration/test_map_errors.py`.

### Checkpoint 0

- All six real `index_not_found` Map cases are path-safe.
- Non-Map compatibility tests remain green.
- No other `src/` file changed.

## I1: Replace Synthetic Error Rows

**Planning correction:** Remove the unreachable parent `map validate` ->
`knowledge_map_validation_failed` applicability cell. Add the real `map validate` ->
`knowledge_map_evidence_stale` owning-path case. Keep
`knowledge_map_validation_failed` covered at its writer transaction owner; do not
synthesize it through a public service or command seam.

- Inventory the parent shared and command-specific cells and create an exact expected
  case-key set.
- Replace public service exception injection with real state fixtures or the narrowest
  owning store/filesystem/index/domain seam.
- Keep the real parser, dispatch, command adapter, and public service entry active for
  every case.
- Assert exact envelope, code, exit, retry/recovery, safe stderr, no ANSI, precedence,
  and artifact-byte preservation for each checked cell.
- Add a regression guard for `MAP_COMMAND.handler` and public service-entry synthesis.

**Primary file:** `tests/integration/test_map_errors.py`.

### Checkpoint A

- The expected and executed applicability sets are identical.
- Focused Map error, security, and recovery tests pass.
- No `src/` file other than the approved `src/repo_dive/cli.py` changed.

## I2: Complete Writer And Capacity Proof

- Add a barrier-coordinated enrichment race against a different public writer.
- Assert exactly one complete winner, one revision conflict, one revision increment,
  strict persisted validity, and no lost semantics.
- Add accepted enrichment growth, exact replay/no-growth, and first-over-limit
  preservation tests using real Evidence and persisted capacities.
- Keep all assertions count/byte based; add no fixed time threshold.

**Primary files:** `tests/integration/test_map_concurrency.py`,
`tests/performance/test_knowledge_map_budget.py`.

### Checkpoint B

- Focused concurrency, lifecycle, store, recovery, and performance suites pass.
- Existing POSIX/Windows lock and atomic-preservation tests remain green.
- No new writer, lock, or product helper exists.

## I3: Correct Bilingual Schema Parity

- Change Index Manifest Schema `1.0` to `2.0` in both architecture files.
- Pin Index Manifest `2.0`, SQLite `5`, Wiki `2.0`, and Knowledge Map `1.0` in the
  closest existing repository documentation contract test.
- Verify matched headings and surrounding technical statements remain equivalent.

**Primary files:** `docs/en/architecture.md`, `docs/zh-CN/architecture.md`, and the
closest existing repository contract test.

## I4: Independent Review And Exact Snapshot

- Dispatch an independent `trellis-check` review against FIC-AC1 through FIC-AC7 and
  parent KM-AC4/KM-AC8/KM-AC9/KM-AC11/KM-AC12.
- Run focused Map error, concurrency, budget, security, recovery, documentation,
  index/retrieval/context/Wiki compatibility, and evaluation tests.
- Run `git diff --check`, `make check`, `make test-unit`, `make test-all`, both
  no-gitignore Ruff commands, and root/Map/six-subcommand help smoke tests.
- Stage only an explicit task allowlist and validate that exact staged snapshot in a
  clean Python 3.11+ worktree. Exclude `.codegraph/`, Host integrations, Wiki product
  code, unrelated task files, and every `docs/superpowers` path.
- Return to parent P3/P4 only after all gates pass.

## Completion Gate

- FIC-AC1 through FIC-AC7 pass with direct evidence.
- The independent reviewer reports no unresolved product or release finding.
- KM-AC4, KM-AC8, KM-AC9, KM-AC11, and KM-AC12 are ready to return to PASS.
- The parent remains free of direct product implementation commits.

## Rollback Point

If I1 exposes another runtime behavior mismatch, stop before changing additional
product code and revise the child design. If an ignored Host path fails only the
dirty-worktree Ruff command, use the required clean snapshot; do not widen the task or
alter Host configuration.
