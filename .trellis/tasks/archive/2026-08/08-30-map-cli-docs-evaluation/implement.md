# Map CLI, Documentation, And Evaluation Implementation Plan

## Dependency Gate

- [ ] Deterministic and Evidence/enrichment child completion gates both pass before D1.
- [ ] Parent command/error/budget contract is unchanged.

## Task D1: Expose Deterministic Map Commands

**Responsibility:** Register `map build`, `map show`, and `map validate` through thin adapters and existing envelopes.

**Acceptance criteria:** exact required flags/help, explicit budgets/result limits, one JSON document, read-only show/validate, no graph/status alias.

**Primary files:**

- `src/repo_dive/commands/map.py`
- `src/repo_dive/cli.py`
- `tests/unit/test_cli.py`
- `tests/integration/test_cli_io.py`
- `tests/integration/test_map_command.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/test_cli.py tests/integration/test_cli_io.py tests/integration/test_map_command.py -q`

## Task D2: Expose Semantic Map Commands

**Responsibility:** Add `map evidence`, `map enrich`, and `map reset` using existing domain services and bounded input.

**Acceptance criteria:** CD-AC1/CD-AC2 semantic paths pass; stdin/file behavior and unchanged/revision responses are stable.

**Dependencies:** D1 and Evidence/enrichment child.

**Primary files:**

- `src/repo_dive/commands/map.py`
- `tests/integration/test_map_command.py`
- `tests/integration/test_map_workflow.py`

**Verification:** `.venv/bin/python -m pytest tests/integration/test_map_command.py tests/integration/test_map_workflow.py -q`

### Checkpoint A

- [ ] D1-D2 CLI/help/I/O/workflow tests pass.
- [ ] JSON stdout contains one document and no ANSI for every subcommand.
- [ ] Existing command help remains unchanged except additive `map` registration.

Rollback: remove `MAP_COMMAND` registration; no artifacts are deleted.

## Task D3: Pin Error, Security, Recovery, And Compatibility Matrix

**Responsibility:** Add one process case for every parent error row and compatibility/failure boundary.

**Acceptance criteria:** CD-AC3/CD-AC4/CD-AC5/CD-AC7; each checked command/error applicability cell and each command-specific row has a case checking bytes, closed retry/recovery enums, precedence, safe diagnostics, and exact exit.

**Dependencies:** D2.

**Primary files:**

- `tests/integration/test_map_errors.py`
- `tests/integration/test_security.py`
- `tests/integration/test_recovery.py`
- `tests/integration/test_wiki_workflow.py`
- `tests/integration/test_hybrid_retrieval.py`

**Verification:** `.venv/bin/python -m pytest tests/integration/test_map_errors.py tests/integration/test_security.py tests/integration/test_recovery.py tests/integration/test_wiki_workflow.py tests/integration/test_hybrid_retrieval.py -q`

## Task D4: Integrate Knowledge Map Evaluation And Performance

**Responsibility:** Execute structural/semantic fixture cases and bounded-scaling checks with separate metrics.

**Acceptance criteria:** CD-AC5/CD-AC6; every heuristic has expected behavior; no semantic truth is inferred from citation presence.

**Dependencies:** D3.

**Primary files:**

- `evals/cases/knowledge_map.jsonl`
- `tests/unit/evaluation/test_runner.py`
- `tests/integration/test_map_evaluation.py`
- `tests/performance/test_knowledge_map_budget.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/evaluation/test_runner.py tests/integration/test_map_evaluation.py tests/performance/test_knowledge_map_budget.py -q`

### Checkpoint B

- [ ] D3-D4 focused tests pass.
- [ ] Existing index/retrieval/context/Wiki suites used by the matrix remain green.
- [ ] `make check` and `make test-unit` pass.

Rollback: remove additive map integration/evaluation cases only if command registration is also rolled back; never weaken existing security tests.

## Task D5: Update Matched Architecture And CLI Contracts

**Responsibility:** Document shipped module boundaries, artifact/revision/lock lifecycle, commands, budgets, errors, and recovery in equivalent pairs.

**Acceptance criteria:** CD-AC8 architecture/CLI pairs have equivalent headings and technical constants and match executable help.

**Dependencies:** D4.

**Primary files:**

- `docs/en/architecture.md`
- `docs/zh-CN/architecture.md`
- `docs/en/cli-contract.md`
- `docs/zh-CN/cli-contract.md`

**Verification:** `.venv/bin/python -m pytest tests/unit/test_repo_contract.py -q`

## Task D6: Add Matched Knowledge Map Workflow

**Responsibility:** Add end-to-end deterministic/optional-semantic workflows, claim example, validation limits, and no-Wiki boundary; update Agent instructions only after commands ship.

**Acceptance criteria:** CD-AC8 workflow pages match; current Wiki sequence remains unchanged; no graph/knowledge-graph naming remains.

**Dependencies:** D5.

**Primary files:**

- `docs/en/knowledge-map-workflow.md`
- `docs/zh-CN/knowledge-map-workflow.md`
- `AGENTS.md`
- `tests/unit/test_repo_contract.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/test_repo_contract.py -q`

### Checkpoint C

- [ ] D5-D6 bilingual headings/constants/error tables are manually compared.
- [ ] Executable help examples parse and run against fixtures.
- [ ] Wiki workflow text/schema remains unchanged.

Rollback: remove workflow pages/instructions with command registration; never leave docs claiming unavailable commands.

## Task D7: Run Clean Release Verification

**Responsibility:** Validate exact intended staged snapshot and all parent acceptance criteria.

**Acceptance criteria:** CD-AC9; no unrelated dirty paths or independent proposal files enter the staged set.

**Dependencies:** D1-D6.

**Primary files:** None expected; failures return to the owning task instead of broad cleanup.

**Verification:**

```bash
make setup
make check
make test-unit
make test-all
git diff --check
.venv/bin/python -m ruff format --check --no-respect-gitignore .
.venv/bin/python -m ruff check --no-respect-gitignore .
```

Also execute `repo-dive --help`, `repo-dive map --help`, all subcommand `--help`, deterministic-only workflow twice with artifact-byte comparison, and one enriched/reset workflow.

### Checkpoint D: Child Completion

- [ ] CD-AC1 through CD-AC9 pass.
- [ ] Parent KM-AC1 through KM-AC12 have recorded evidence.
- [ ] Full-scope code review has no unresolved finding.
- [ ] Return to parent final integration review; do not archive parent automatically.

Rollback: remove public registration and matched docs first; preserve repository-owned artifacts and previous commands.
