# Knowledge Graph Implementation Plan

**Status:** Draft; implementation not started
**Date:** 2026-08-30
**PRD:** `../specs/2026-08-30-knowledge-graph-prd.md`
**Technical specification:** `../specs/2026-08-30-knowledge-graph-design.md`

## 1. Outcome

Implement an additive `repo-dive graph` workflow that materializes deterministic repository facts, packages per-unit Evidence, validates calling-agent semantics, and atomically publishes architecture, flow, reading-tour, and Wiki-topic projections.

This plan does not authorize implementation. It is the standalone review artifact requested for the Knowledge Graph initiative. The existing Trellis task and `tasks/todo.md` remain unchanged until the plan is approved.

## 2. Delivery Strategy

Work proceeds in vertical, testable slices:

```text
contracts
  -> initialize and inspect facts
  -> collect one unit's Evidence
  -> submit one semantic unit
  -> validate and publish projections
  -> expose the complete CLI workflow
```

Each task touches at most five primary files. Tests are written first for every behavior change. Checkpoints occur after every two or three tasks.

## 3. Architectural Decisions Carried into Implementation

- New domain package: `src/repo_dive/knowledge/`.
- New command adapter: `src/repo_dive/commands/graph.py`.
- Private index access remains behind `IndexStore`/reader protocols.
- Working state and metadata live under `.repo-dive/graph/`.
- Stable output is `.repo-dive/knowledge-graph.json`.
- Agent semantics cannot create or modify fact nodes or fact edges.
- Required Evidence is reserved before supplemental Evidence.
- Wiki topics remain advisory; current Wiki behavior is unchanged.
- No runtime dependency is added.
- No model provider is instantiated by graph code.

## 4. Dependency Graph

```text
Task 1: contracts
    |
    +--> Task 2: persistence
    |
    +--> Task 3: bounded index inventory
             |
             +--> Task 4: fact materialization
                      |
                      +--> Task 5: component derivation
                      |
                      +--> Task 6: flow derivation
                               |
                               +--> Task 7: init/status service
                                        |
                                        +--> Task 8: Evidence planning
                                                 |
                                                 +--> Task 9: Evidence persistence
                                                          |
                                                          +--> Task 10: semantic submission
                                                                    |
                                                                    +--> Task 11: projections
                                                                              |
                                                                              +--> Task 12: validate/build
                                                                                       |
                                                                                       +--> Task 13: CLI
                                                                                                |
                                                                                                +--> Task 14: recovery/security
                                                                                                         |
                                                                                                         +--> Task 15: docs/evaluation
```

Tasks 5 and 6 can be implemented in parallel after Task 4 because they consume the same immutable fact graph. Other tasks are sequential at their public contract boundaries.

## 5. Phase 1 — Contracts and Storage

### Task 1: Define Knowledge Graph 1.0 models and strict decoders

**Description:** Add immutable values for source identity, fact nodes, fact edges, provenance, components, flows, semantic units, Evidence snapshots, projections, state, and the published artifact. Add canonical serialization, stable hashing, enum registries, and boundary validation.

**Acceptance criteria:**

- [ ] Every Spec Section 7 type has an immutable typed model.
- [ ] Decoders reject unknown fields, invalid enums, absolute paths, invalid line ranges, dangling local references, and unsupported schema versions.
- [ ] Canonical serialization and hashes are byte-stable and exclude timestamps.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_models.py -q`
- [ ] Repeat-run fixture produces equal canonical bytes and hashes.
- [ ] Negative fixtures assert stable validation codes, not implementation messages.

**Dependencies:** None.

**Files likely touched:**

- `src/repo_dive/knowledge/__init__.py`
- `src/repo_dive/knowledge/models.py`
- `src/repo_dive/knowledge/validation.py`
- `tests/unit/knowledge/__init__.py`
- `tests/unit/knowledge/test_models.py`

**Estimated scope:** Medium, 5 files.

### Task 2: Add graph artifact paths and atomic working-state storage

**Description:** Extend the storage boundary for graph-specific state, metadata, and the stable public artifact. Implement exact read/decode/write behavior and optimistic state-hash checks.

**Acceptance criteria:**

- [ ] Graph paths resolve only below the validated repository root.
- [ ] State, metadata, and publication writes use atomic replace.
- [ ] A prior-state hash mismatch returns `graph_state_conflict` without changing files.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_store.py tests/unit/storage/test_paths.py -q`
- [ ] Failure injection proves the last valid file survives.

**Dependencies:** Task 1.

**Files likely touched:**

- `src/repo_dive/storage/paths.py`
- `src/repo_dive/knowledge/store.py`
- `tests/unit/knowledge/test_store.py`
- `tests/unit/storage/test_paths.py`

**Estimated scope:** Medium, 4 files.

### Checkpoint A: Contract foundation

- [ ] `make check` passes.
- [ ] Focused unit tests pass.
- [ ] Review public field names, enum values, artifact paths, and error codes before they acquire consumers.
- [ ] Confirm no Wiki artifact or schema changed.

## 6. Phase 2 — Deterministic Fact Graph

### Task 3: Expose bounded, stable index inventory interfaces

**Description:** Add supported reader methods for counting and paginating indexed files, symbols, relationships, and source identity. Keep raw SQLite access inside `indexing`.

**Acceptance criteria:**

- [ ] Inventory methods require positive limits and use stable sort keys.
- [ ] Pagination across a fixed index build has no duplicates or omissions.
- [ ] Knowledge Graph code can enumerate facts without importing SQLite details.

**Verification:**

- [ ] `pytest tests/unit/indexing/test_store.py tests/unit/indexing/test_graph.py -q`
- [ ] Contract tests cover empty, one-page, and multi-page indexes.

**Dependencies:** Task 1.

**Files likely touched:**

- `src/repo_dive/indexing/graph.py`
- `src/repo_dive/indexing/store.py`
- `tests/unit/indexing/test_graph.py`
- `tests/unit/indexing/test_store.py`

**Estimated scope:** Medium, 4 files.

### Task 4: Materialize bounded fact nodes and edges

**Description:** Convert index inventory into public repository, file, and symbol nodes plus normalized fact edges. Enforce deterministic inclusion order, endpoint closure, provenance precision, budget accounting, and truncation metadata.

**Acceptance criteria:**

- [ ] Same index and budgets produce byte-identical fact graphs.
- [ ] No included edge has a missing endpoint.
- [ ] Every omitted fact is reflected in stable counts and reason categories.
- [ ] Too-small essential budgets fail without persisting state.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_materializer.py -q`
- [ ] Budget-boundary and ordering fixtures pass.

**Dependencies:** Tasks 1 and 3.

**Files likely touched:**

- `src/repo_dive/knowledge/materializer.py`
- `src/repo_dive/knowledge/models.py`
- `tests/unit/knowledge/test_materializer.py`
- `tests/fixtures/knowledge_graph/fact_inventory.json`

**Estimated scope:** Medium, 4 files.

### Task 5: Derive deterministic components and dependency edges

**Description:** Implement the `package_scope_v1` grouping hierarchy and aggregate cross-component fact relationships into transparent component dependencies.

**Acceptance criteria:**

- [ ] Empty, single-file, package, and monorepo fixtures produce stable component membership.
- [ ] Aggregated dependencies list contributing fact-edge IDs and confidence bounds.
- [ ] Cycles are represented without changing dependency direction.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_components.py -q`
- [ ] Expected component membership and dependency snapshots match fixtures.

**Dependencies:** Task 4.

**Files likely touched:**

- `src/repo_dive/knowledge/components.py`
- `src/repo_dive/knowledge/models.py`
- `tests/unit/knowledge/test_components.py`
- `tests/fixtures/knowledge_graph/component_cases.json`

**Estimated scope:** Medium, 4 files.

### Task 6: Derive bounded static flow candidates

**Description:** Add a versioned entrypoint registry and stable bounded traversal for static flow candidates. Record root signals, step edges, terminal reasons, confidence, and truncation.

**Acceptance criteria:**

- [ ] Only registered deterministic entrypoint signals create flows.
- [ ] Traversal respects depth, edge kinds, confidence, and global budgets.
- [ ] A repository with no supported entrypoint reports zero flows without guessing.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_flows.py -q`
- [ ] Linear, branching, cyclic, and no-entrypoint fixtures pass.

**Dependencies:** Task 4.

**Files likely touched:**

- `src/repo_dive/knowledge/flows.py`
- `src/repo_dive/knowledge/entrypoints.py`
- `tests/unit/knowledge/test_flows.py`
- `tests/fixtures/knowledge_graph/flow_cases.json`

**Estimated scope:** Medium, 4 files.

### Checkpoint B: Deterministic facts

- [ ] `make check` passes.
- [ ] `make test-unit` passes.
- [ ] Repeat-run snapshots are byte-identical.
- [ ] Review every heuristic against an evaluation fixture.
- [ ] Confirm no generative or graph-database dependency was added.

## 7. Phase 3 — Initialization and Evidence

### Task 7: Implement graph initialization, reuse, and status

**Description:** Orchestrate materialization, component/flow unit creation, incremental comparison with prior state, per-unit invalidation, and a deterministic status result.

**Acceptance criteria:**

- [ ] First initialization creates schema-valid working state and metadata.
- [ ] Same source and budgets return `unchanged: true` without rewriting files.
- [ ] Source changes preserve only units whose membership and referenced fact content remain valid.
- [ ] Status reports unit counts, truncation, identity, and next valid actions.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_service_init.py -q`
- [ ] Granular invalidation fixtures preserve one unaffected generated unit and stale one affected unit.

**Dependencies:** Tasks 2, 5, and 6.

**Files likely touched:**

- `src/repo_dive/knowledge/service.py`
- `src/repo_dive/knowledge/store.py`
- `tests/unit/knowledge/test_service_init.py`
- `tests/fixtures/knowledge_graph/incremental_cases.json`

**Estimated scope:** Medium, 4 files.

### Task 8: Build per-unit Evidence query plans

**Description:** Derive deterministic required anchors and supplemental retrieval queries for component, flow, repository-summary, and reading-tour units.

**Acceptance criteria:**

- [ ] Every unit kind has a versioned query-plan builder.
- [ ] Required anchors are deterministic and reference current fact nodes.
- [ ] Query plans expose their inputs and stable query hash.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_evidence_plans.py -q`
- [ ] Fixture snapshots prove stable required/supplemental selection.

**Dependencies:** Task 7.

**Files likely touched:**

- `src/repo_dive/knowledge/evidence.py`
- `src/repo_dive/knowledge/models.py`
- `tests/unit/knowledge/test_evidence_plans.py`
- `tests/fixtures/knowledge_graph/evidence_plans.json`

**Estimated scope:** Medium, 4 files.

### Task 9: Collect and persist graph Evidence snapshots

**Description:** Reuse retrieval and `EvidencePacker` to reserve complete required chunks, add ranked supplemental chunks, emit the generation contract, and atomically persist the snapshot.

**Acceptance criteria:**

- [ ] Required chunks are reserved before supplemental chunks.
- [ ] Insufficient required budget returns `graph_required_evidence_budget` and persists nothing.
- [ ] Successful snapshots bind repository, index, unit membership, query, budget, and Evidence hashes.
- [ ] Evidence response ordering and IDs are stable.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_evidence.py tests/unit/context/test_packer.py -q`
- [ ] An integration fixture proves no partial required chunk is returned.

**Dependencies:** Tasks 7 and 8.

**Files likely touched:**

- `src/repo_dive/knowledge/evidence.py`
- `src/repo_dive/knowledge/service.py`
- `tests/unit/knowledge/test_evidence.py`
- `tests/integration/test_graph_evidence.py`

**Estimated scope:** Medium, 4 files.

### Checkpoint C: Context-to-generate boundary

- [ ] `make check` passes.
- [ ] `make test-unit` passes.
- [ ] A real fixture reaches `evidence_ready` with exactly one JSON result.
- [ ] Review the generation contract as untrusted-data input/output.
- [ ] Confirm graph Evidence is persisted separately from Wiki Evidence.

## 8. Phase 4 — Agent Semantics and Projections

### Task 10: Validate and persist semantic unit submissions

**Description:** Decode one agent JSON document, enforce Evidence citations and fact references, calculate the canonical submission hash, apply state/idempotence rules, and persist the generated unit.

**Acceptance criteria:**

- [ ] Every summary, responsibility, concept, relationship, and step explanation has valid Evidence IDs.
- [ ] Unknown fact nodes, Evidence IDs, concept endpoints, fields, and relation kinds are rejected.
- [ ] Identical resubmission succeeds with `unchanged: true`; different content for a generated unit fails.
- [ ] Stale membership or Evidence is rejected before any state write.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_submission.py -q`
- [ ] Property-style negative cases cover dangling references and reused intent with different payload.

**Dependencies:** Task 9.

**Files likely touched:**

- `src/repo_dive/knowledge/submission.py`
- `src/repo_dive/knowledge/service.py`
- `tests/unit/knowledge/test_submission.py`
- `tests/fixtures/knowledge_graph/submissions.json`

**Estimated scope:** Medium, 4 files.

### Task 11: Assemble deterministic projections

**Description:** Combine validated facts and semantic units into architecture, static-flow, reading-tour, and advisory Wiki-topic projections with stable ordering and hashes.

**Acceptance criteria:**

- [ ] Architecture membership/dependencies remain fact-owned; prose remains semantic-owned.
- [ ] Flow steps expose static-analysis coverage and truncation.
- [ ] Reading order is deterministic across cycles and disconnected components.
- [ ] Wiki topics do not contain governed Wiki page IDs or mutate Wiki state.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_projections.py -q`
- [ ] Projection fixtures reject dangling and forbidden cyclic references.

**Dependencies:** Task 10.

**Files likely touched:**

- `src/repo_dive/knowledge/projections.py`
- `src/repo_dive/knowledge/models.py`
- `tests/unit/knowledge/test_projections.py`
- `tests/fixtures/knowledge_graph/projections.json`

**Estimated scope:** Medium, 4 files.

### Task 12: Validate working state and atomically publish

**Description:** Implement full-graph validation and publication from one immutable state snapshot. Preserve the previous public artifact on every failure path.

**Acceptance criteria:**

- [ ] Validation checks schema, identities, hashes, unit completion, citations, referential integrity, ordering, and projection consistency.
- [ ] Build refuses incomplete, stale, failed, or invalid state.
- [ ] Successful build writes one canonical Knowledge Graph 1.0 artifact atomically.
- [ ] Failed validation or replace leaves the previous artifact byte-identical.

**Verification:**

- [ ] `pytest tests/unit/knowledge/test_build.py tests/integration/test_graph_workflow.py -q`
- [ ] Failure-injection test proves last-valid-artifact preservation.

**Dependencies:** Tasks 2 and 11.

**Files likely touched:**

- `src/repo_dive/knowledge/service.py`
- `src/repo_dive/knowledge/validation.py`
- `tests/unit/knowledge/test_build.py`
- `tests/integration/test_graph_workflow.py`

**Estimated scope:** Medium, 4 files.

### Checkpoint D: Domain-complete workflow

- [ ] `make check` passes.
- [ ] `make test-unit` passes.
- [ ] An in-process workflow reaches a byte-stable published artifact.
- [ ] Adversarial review covers unsupported claims, stale Evidence, dangling references, and atomicity.

## 9. Phase 5 — CLI, Recovery, and Documentation

### Task 13: Add the `repo-dive graph` command family

**Description:** Wire `init`, `evidence`, `unit`, `status`, `validate`, and `build` through a thin command adapter and CLI parser. Preserve exactly-one-JSON stdout and the repository exit-code mapping.

**Acceptance criteria:**

- [ ] Executable help lists every specified command and flag.
- [ ] JSON success and error paths emit exactly one document on stdout.
- [ ] Diagnostics go to stderr without ANSI in JSON mode.
- [ ] No command has an implicit unbounded graph, result, or token budget.

**Verification:**

- [ ] `pytest tests/unit/test_cli.py tests/unit/test_cli_errors.py tests/integration/test_graph_cli.py -q`
- [ ] Shell-level stdin and stdout tests parse the result as exactly one JSON document.

**Dependencies:** Task 12.

**Files likely touched:**

- `src/repo_dive/commands/graph.py`
- `src/repo_dive/commands/__init__.py`
- `src/repo_dive/cli.py`
- `tests/unit/test_cli.py`
- `tests/integration/test_graph_cli.py`

**Estimated scope:** Medium, 5 files.

### Task 14: Add recovery, security, and compatibility integration tests

**Description:** Exercise stale indexes, stale Evidence, invalid repository paths, oversized JSON, concurrent state changes, write failures, interrupted workflows, and existing Wiki compatibility at the process boundary.

**Acceptance criteria:**

- [ ] Every stable graph error code maps to the specified exit code and recovery action.
- [ ] Path traversal, absolute paths, oversized input, and source-content diagnostic leakage are rejected.
- [ ] Existing index, context, and Wiki integration tests pass unchanged.

**Verification:**

- [ ] `pytest tests/integration/test_graph_recovery.py tests/integration/test_security.py tests/integration/test_wiki_workflow.py -q`
- [ ] `make test-all` passes.

**Dependencies:** Task 13.

**Files likely touched:**

- `tests/integration/test_graph_recovery.py`
- `tests/integration/test_security.py`
- `tests/integration/test_cli_io.py`
- `tests/integration/test_wiki_workflow.py`

**Estimated scope:** Medium, 4 files.

### Task 15: Add paired user documentation and evaluation cases

**Description:** Document the shipped command workflow in matched English and Chinese pages, update architecture/CLI contracts only after executable behavior exists, and add quality fixtures for known components and flows.

**Acceptance criteria:**

- [ ] English and Chinese Knowledge Graph workflow pages have equivalent headings and contracts.
- [ ] Architecture and CLI documents distinguish index facts, agent semantics, graph projections, and Wiki ownership.
- [ ] Evaluation fixtures measure determinism, grounding, structural validity, coverage, and incremental invalidation.
- [ ] Documentation never claims unshipped commands are implemented.

**Verification:**

- [ ] `make check` passes documentation/repository contract checks.
- [ ] `make test-all` passes evaluation and release-contract tests.
- [ ] Manual comparison confirms English/Chinese command examples and error tables match.

**Dependencies:** Tasks 13 and 14.

**Files likely touched:**

- `docs/en/knowledge-graph-workflow.md`
- `docs/zh-CN/knowledge-graph-workflow.md`
- `docs/en/architecture.md`
- `docs/zh-CN/architecture.md`
- evaluation manifest or one focused evaluation fixture selected during implementation

**Estimated scope:** Medium, 5 files.

### Checkpoint E: Release candidate

- [ ] Fresh environment: `make setup`.
- [ ] Static and contract checks: `make check`.
- [ ] Unit suite: `make test-unit`.
- [ ] Full suite: `make test-all`.
- [ ] Repeat full workflow twice and compare public artifact bytes.
- [ ] Confirm `repo-dive --help` and `repo-dive graph --help` match documentation.
- [ ] Confirm the last valid graph and Wiki artifacts survive graph failure cases.
- [ ] Human review approves public contracts and release notes.

## 10. Test Matrix

| Scenario | Expected result | Primary level |
|---|---|---|
| Same index and budgets initialized twice | Second result is unchanged; state bytes stable | Unit + integration |
| Node budget cannot include root and one file | Exit 2, no state write | Unit + CLI |
| Graph is intentionally truncated | Counts and reasons visible; validation succeeds | Unit + integration |
| Required Evidence exceeds token budget | Exit 2, no snapshot write | Unit + integration |
| Agent references unknown Evidence | Exit 2, state unchanged | Unit + CLI |
| Identical unit resubmission | Success, `unchanged: true` | Unit + integration |
| Different unit resubmission | Exit 2, current unit preserved | Unit + integration |
| One source component changes | Only affected units become stale | Unit + integration |
| Build with pending unit | Exit 3, last artifact preserved | Integration |
| Atomic replace fails | Exit 4, last artifact preserved | Unit + integration |
| No recognized entrypoint | Valid graph with zero flows and coverage note | Unit + evaluation |
| Cyclic components | Stable dependency and reading-tour grouping | Unit + evaluation |
| Existing Wiki flow with graph files present | Wiki output unchanged | Integration |
| JSON process output | Exactly one JSON document, no ANSI | CLI integration |

## 11. Risks and Mitigations

| Risk | Impact | Early signal | Mitigation |
|---|---|---|---|
| Public identity is unstable | High | Line-only edit changes many unit IDs | Test line-movement fixtures in Task 1 before consumers exist |
| Bounded graph loses important facts | High | Known fixture component/flow disappears | Transparent priority rules, omission counts, evaluation fixtures |
| Required Evidence explodes for large units | High | Minimum token count exceeds practical budgets | Deterministic representative anchors and smaller unit scopes |
| Relationship coverage is language-dependent | Medium | Mixed-language fixture reports sparse flows | Coverage metadata and no unsupported inference |
| Incremental reuse is too permissive | High | Stale semantic unit remains generated | Hash membership, fact content, and Evidence; invalidate conservatively |
| Incremental reuse is too conservative | Medium | Most units regenerate after local edits | Stable public IDs and per-unit hashes; fixture-driven tuning |
| CLI contract diverges from Wiki commands | Medium | Different envelope/error behavior | Reuse command adapter patterns and shared CLI tests |
| Working-state size becomes excessive | Medium | Large state fixtures dominate runtime/disk | Explicit budgets, compact canonical JSON, performance test before release |

## 12. Performance Guardrails

Version 1 does not promise fixed wall-clock targets across hardware, but it must preserve bounded complexity:

- index inventory is paginated;
- fact materialization is linear in included nodes and relationships plus stable sorting;
- traversal is bounded by depth, node, and edge budgets;
- no all-pairs path computation;
- no unbounded source reads;
- semantic submission validation is linear in submitted collection size;
- publication uses one canonical serialization pass.

Add a performance test using a generated index fixture that verifies memory and result counts remain bounded by supplied budgets. Any numeric threshold should be calibrated in CI before it becomes a release contract.

## 13. Rollout

1. Ship as an optional additive command family.
2. Keep Wiki behavior independent.
3. Mark the artifact schema as `1.0` and validate strictly.
4. Exercise the workflow against small, medium, truncated, cyclic, and mixed-language fixtures.
5. Publish documentation only when `--help` and integration tests prove commands exist.
6. Gather fixture-based quality results before proposing automatic Wiki consumption.

## 14. Rollback

Because the feature is additive, rollback consists of removing or disabling the `graph` command adapter while leaving existing index and Wiki code paths unchanged. Existing `.repo-dive/graph/` and `.repo-dive/knowledge-graph.json` files are repository-owned data and must not be deleted automatically. A later compatible implementation may read them by schema version.

## 15. Deferred Follow-ups

- Exact call-site relationship locations in the index schema.
- An explicit semantic-unit reset/regeneration command.
- Deterministic Markdown rendering of the published graph.
- Interactive HTML or graph visualization.
- Automatic or flag-gated Wiki Evidence integration.
- Cross-repository graphs.
- Additional language-specific entrypoint registries.

Each follow-up requires its own approved specification because it changes a public contract, a source boundary, or both.

## 16. Approval Checklist

- [ ] PRD scope and out-of-scope items are accepted.
- [ ] Capability map and dependency direction are accepted.
- [ ] CLI commands, artifact paths, schemas, and error semantics are accepted.
- [ ] Advisory-only Wiki boundary is accepted.
- [ ] Each task has testable acceptance criteria and a verification command.
- [ ] No task exceeds five primary files.
- [ ] Checkpoints and full completion gates are sufficient.
- [ ] Implementation is explicitly authorized in a later request.
