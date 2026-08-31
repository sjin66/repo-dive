# Deterministic Knowledge Map Implementation Plan

## Dependency Gate

- [ ] `08-30-relationship-provenance-index-schema` is complete and its structural retrieval regression suite is green.
- [ ] Parent naming, budget, lifecycle, lock, and error contracts remain unchanged.

## Task B1: Define Strict Artifact And Budget Models

**Responsibility:** Implement complete Schema 1.0 types, canonical serialization/hashes, IDs, strict decoder, and empty semantic slots.

**Acceptance criteria:** DM-AC1; no source-chunk node; parent-exact scope contract, Evidence snapshot, and enrichment projections round-trip strictly; canonical input byte/hash metrics are frozen; unknown fields and dangling references fail closed.

**Primary files:**

- `src/repo_dive/knowledge_map/__init__.py`
- `src/repo_dive/knowledge_map/models.py`
- `tests/unit/knowledge_map/test_models.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_models.py -q`

## Task B2: Implement Shared Lock And Revision Store

**Responsibility:** Add strict artifact reads, bounded OS advisory lock, index/reference recheck, pure exact-equivalence hook, expected revision/hash CAS for remaining mutations, validated atomic replacement, and failure preservation.

**Acceptance criteria:** DM-AC2; exact already-applied intent can return unchanged after baseline drift, non-equivalent drift conflicts, and invalid baseline/absent-state races are covered.

**Dependencies:** B1.

**Primary files:**

- `src/repo_dive/knowledge_map/store.py`
- `tests/unit/knowledge_map/test_store.py`
- `tests/integration/test_map_concurrency.py`
- `tests/integration/test_recovery.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_store.py tests/integration/test_map_concurrency.py tests/integration/test_recovery.py -q`

### Checkpoint A

- [ ] B1-B2 focused tests pass.
- [ ] `git diff --check` reports no artifact/model drift.
- [ ] Review the lock protocol for TOCTOU and Windows/POSIX release behavior.

Rollback: remove the additive package/store; relationship Schema remains valid.

## Task B3: Expose And Consume Bounded Index Snapshot

**Responsibility:** Add supported stable index paging/count interfaces and a read-only Knowledge Map snapshot/coverage adapter.

**Acceptance criteria:** DM-AC3; no raw SQL outside indexing; malformed/oversized manifest observations are safe.

**Dependencies:** B1 and relationship child.

**Primary files:**

- `src/repo_dive/indexing/store.py`
- `src/repo_dive/knowledge_map/snapshot.py`
- `tests/unit/indexing/test_store.py`
- `tests/unit/knowledge_map/test_snapshot.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/indexing/test_store.py tests/unit/knowledge_map/test_snapshot.py -q`

## Task B4: Resolve Supported Python References

**Responsibility:** Implement ordered conservative resolution, bounded ambiguity, and derived `resolves_to` traceability.

**Acceptance criteria:** exact/relative/alias/unique/ambiguous/unresolved fixtures are stable; non-Python remains unresolved.

**Dependencies:** B3.

**Primary files:**

- `src/repo_dive/knowledge_map/resolution.py`
- `tests/unit/knowledge_map/test_resolution.py`
- `tests/fixtures/knowledge_map/resolution_cases.json`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_resolution.py -q`

## Task B5: Lift File And Module Graphs

**Responsibility:** Build repository/file/module/symbol nodes and aggregate occurrence edges under endpoint/output budgets.

**Acceptance criteria:** DM-AC4; unique and occurrence metrics, confidence, contributors, omission reasons, and module rules are pinned.

**Dependencies:** B4.

**Primary files:**

- `src/repo_dive/knowledge_map/lifting.py`
- `tests/unit/knowledge_map/test_lifting.py`
- `tests/fixtures/knowledge_map/lifting_cases.json`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_lifting.py -q`

### Checkpoint B

- [ ] `.venv/bin/python -m pytest tests/unit/knowledge_map/test_snapshot.py tests/unit/knowledge_map/test_resolution.py tests/unit/knowledge_map/test_lifting.py -q`
- [ ] Source-fact overflow and endpoint closure cases write nothing.
- [ ] `make check`

Rollback: retain B1-B2 contracts, remove derivation modules, and return to planning if source facts are insufficient.

## Task B6: Compute Explainable Importance

**Responsibility:** Persist raw unique-neighbor signals and exact lexicographic rank.

**Acceptance criteria:** repeated occurrences do not inflate fan-in/out; entrypoint/API/docs/test/bridge/tie fixtures and evaluation expectations pass.

**Dependencies:** B5.

**Primary files:**

- `src/repo_dive/knowledge_map/analysis.py`
- `tests/unit/knowledge_map/test_analysis.py`
- `evals/cases/knowledge_map.jsonl`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_analysis.py -q`

## Task B7: Derive Clusters, SCCs, And Layers

**Responsibility:** Implement deterministic package/directory grouping, undersized merge, Tarjan SCC, closed layer rules, and unclassified fallback.

**Acceptance criteria:** DM-AC5 topology cases cover empty/single/package/monorepo/cycle/tie/conflict/unknown.

**Dependencies:** B5.

**Primary files:**

- `src/repo_dive/knowledge_map/topology.py`
- `tests/unit/knowledge_map/test_topology.py`
- `evals/cases/knowledge_map.jsonl`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_topology.py -q`

### Checkpoint C

- [ ] B6-B7 focused tests pass.
- [ ] Evaluation records identify the exact heuristic/rule version.
- [ ] No hidden scalar score or stochastic dependency exists.

Rollback: versioned analysis/topology rules can revert independently before consumers ship.

## Task B8: Derive Static Flows And Tour

**Responsibility:** Implement closed roots/transitions, bounded stable traversal, terminal/truncation metadata, and deterministic tour.

**Acceptance criteria:** DM-AC5 flow/tour cases cover linear/branch/cycle/no-root/sparse/truncated/utility/bridge/tie behavior.

**Dependencies:** B6, B7.

**Primary files:**

- `src/repo_dive/knowledge_map/flows.py`
- `tests/unit/knowledge_map/test_flows.py`
- `tests/fixtures/knowledge_map/flow_cases.json`
- `evals/cases/knowledge_map.jsonl`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_flows.py -q`

## Task B9: Orchestrate Deterministic Build Lifecycle

**Responsibility:** Compose snapshot through tour, implement no-op/capacity/rebuild invalidation matrix, and publish through `MapWriteTransaction`.

**Acceptance criteria:** DM-AC6/DM-AC7; deterministic-only artifact validates; scope contracts match exact cluster/flow/tour expansion and permissions; concurrent semantics are never overwritten; semantic-capacity reductions below snapshot/reference/claim/canonical-input usage fail without mutation.

**Dependencies:** B2-B8.

**Primary files:**

- `src/repo_dive/knowledge_map/build.py`
- `tests/unit/knowledge_map/test_build.py`
- `tests/integration/test_map_workflow.py`
- `tests/integration/test_map_concurrency.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_build.py tests/integration/test_map_workflow.py tests/integration/test_map_concurrency.py -q`

## Task B10: Implement Pure Bounded Views

**Responsibility:** Project architecture, flows, and tour from one validated snapshot with explicit result limits.

**Acceptance criteria:** DM-AC8; projections expose identity/coverage/truncation/semantic availability and never mutate bytes.

**Dependencies:** B9.

**Primary files:**

- `src/repo_dive/knowledge_map/views.py`
- `tests/unit/knowledge_map/test_views.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_views.py -q`

### Checkpoint D

- [ ] `.venv/bin/python -m pytest tests/unit/knowledge_map tests/integration/test_map_workflow.py tests/integration/test_map_concurrency.py -q`
- [ ] `.venv/bin/python -m pytest tests/performance -q`
- [ ] `make check`
- [ ] Existing Wiki tests show no Knowledge Map dependency.

Rollback: remove unregistered deterministic package/artifact support; do not revert Child 1 facts.

## Completion Gate

- [ ] DM-AC1 through DM-AC9 pass.
- [ ] Shared model/store APIs and exact scope contract/Evidence/enrichment projections are frozen for Child 3.
- [ ] No public CLI, Wiki, plugin, or published product documentation changed.
