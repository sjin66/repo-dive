# Knowledge Map Integration Corrections Implementation Plan

## Task I1: Correct Map Invocation Envelopes

- Add failing subprocess/process tests for unsupported Map format and invalid flags.
- Route Map parser failures through the existing Schema 1.0 error envelope with exit
  `2`, safe stderr, and no ANSI.
- Verify all root and Map help output plus existing CLI parser tests.

**Primary files:** `src/repo_dive/cli.py`, `src/repo_dive/commands/map.py`,
`tests/integration/test_map_errors.py`, `tests/unit/test_cli_errors.py`.

## Task I2: Close Persisted Scope Validation

- Add model tests constructing and decoding a correctly rehashed artifact whose claim
  uses a wrong-scope fact or related node.
- Enforce scope-owned claim references in strict artifact validation without changing
  the permission tables or submission schema.

**Primary files:** `src/repo_dive/knowledge_map/models.py`,
`tests/unit/knowledge_map/test_models.py`.

### Checkpoint A

- Invocation failures produce one JSON envelope.
- Strict creation/decode rejects wrong-scope semantic references.
- Existing model and CLI tests pass.

## Task I3: Replace Simulated Process Matrix Coverage

- Remove tests that replace `MAP_COMMAND.handler` solely to raise expected errors.
- Exercise real dispatch and inject only at service/store/filesystem seams.
- Cover every checked parent applicability cell and command-specific row with exact
  code/exit/recovery/no-write/precedence assertions.

**Primary files:** `tests/integration/test_map_errors.py`,
`tests/integration/test_map_command.py`, `tests/integration/test_security.py`,
`tests/integration/test_recovery.py`.

## Task I4: Complete Writer And Bounded-Work Evidence

- Add coordinated cross-writer contention/equivalence/conflict tests.
- Cover Windows lock adapter branches.
- Expand bounded tests across artifact serialization, flow/tour, Evidence capacities,
  and repeated semantic replay/growth.

**Primary files:** `tests/integration/test_map_concurrency.py`,
`tests/performance/test_knowledge_map_budget.py`, existing Knowledge Map unit/integration
tests where the closest observable contract already lives.

### Checkpoint B

- Parent KM-AC4, KM-AC8, KM-AC9, and KM-AC11 have direct executable evidence.
- No new writer/lock/dependency or fixed latency assertion exists.
- Security, recovery, and performance suites pass.

## Task I5: Correct Matched Documentation And Traceability

- Update both architecture files to index Schema `5`.
- Update both Wiki generation-flow files to Wiki Schema `2.0`.
- Recheck Map CLI/workflow pairs and executable help constants.
- Record comparison-only/superseded status in parent task traceability without editing
  any `docs/superpowers` file.

**Primary files:** `docs/en/architecture.md`, `docs/zh-CN/architecture.md`,
`docs/en/wiki-generation-flow.md`, `docs/zh-CN/wiki-generation-flow.md`, parent task
metadata/plan, and repository contract tests.

## Task I6: Independent Review And Clean Snapshot

- Run focused model/CLI/process/concurrency/security/recovery/performance/docs tests.
- Run `make check`, `make test-unit`, `make test-all`, `git diff --check`, both
  no-gitignore Ruff checks, and root/Map/all subcommand help smoke tests.
- Stage with an explicit allowlist; exclude `.codegraph/`, Host skills/hooks, and all
  `docs/superpowers` files; validate the exact staged Python 3.11+ snapshot.
- Return to parent P3/P4 review after this child independently passes.

## Completion Gate

- IC-AC1 through IC-AC7 pass.
- Parent blockers have direct regression tests and no unresolved product finding.
- No historical comparison proposal, Wiki code, plugin, or unrelated file changed.

## Rollback

If any correction requires a new product contract rather than enforcement of the
existing one, stop and return to parent planning. Never patch around the shared writer
or broaden scope permissions.
