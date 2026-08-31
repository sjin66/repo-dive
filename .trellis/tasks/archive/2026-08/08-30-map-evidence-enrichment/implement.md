# Map Evidence And Enrichment Implementation Plan

## Dependency Gate

- [ ] Deterministic child DM-AC1/DM-AC2/DM-AC6/DM-AC7 pass.
- [ ] `models.py`, `store.py`, `MapWriteTransaction`, and build invalidation are frozen.
- [ ] Parent claim, budget, error, and reset contracts remain approved.

## Task C1: Build Pure Scope Evidence Plans

**Responsibility:** Derive required anchors, supplemental query, scope contract, and stable query hash without writing.

**Acceptance criteria:** ME-AC1 plan fixtures cover exact cluster/flow/tour expansion, record/claim permissions, representative fallback/tie ordering, empty/sparse scopes, stable query hashes, and wrong-scope IDs.

**Primary files:**

- `src/repo_dive/knowledge_map/evidence.py`
- `tests/unit/knowledge_map/test_evidence.py`
- `tests/fixtures/knowledge_map/evidence_cases.json`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_evidence.py -q`

## Task C2: Collect And Persist Scope Evidence

**Responsibility:** Reserve direct chunks, add supplemental retrieval, produce response contract, and persist through shared transaction.

**Acceptance criteria:** ME-AC2/ME-AC3; insufficient required budget writes nothing; equivalent snapshot unchanged; cited replacement conflicts.

**Dependencies:** C1.

**Primary files:**

- `src/repo_dive/knowledge_map/evidence_service.py`
- `tests/unit/knowledge_map/test_evidence_service.py`
- `tests/integration/test_map_evidence.py`
- `tests/unit/context/test_packer.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_evidence_service.py tests/integration/test_map_evidence.py tests/unit/context/test_packer.py -q`

### Checkpoint A

- [ ] C1-C2 focused tests pass.
- [ ] Exit `3` required-Evidence budget and no-write behavior are pinned.
- [ ] Review response for source/path privacy and complete-chunk boundaries.

Rollback: remove Evidence services; deterministic map remains valid.

## Task C3: Decode And Validate Claim-Level Input

**Responsibility:** Implement exact schema, bounded claims, closed enums, per-claim fact/Evidence references, and safe validation errors.

**Acceptance criteria:** ME-AC4/ME-AC5; no record-level citation/title/association field; labels and related nodes occur only in cited claims; exact scope-kind permission tables apply; canonical payload bytes/hash exclude expected revision; fact-mutating fields and unknown/dangling references fail.

**Dependencies:** C2 for scope contract fixtures.

**Primary files:**

- `src/repo_dive/knowledge_map/submission.py`
- `tests/unit/knowledge_map/test_submission.py`
- `tests/fixtures/knowledge_map/enrichment_cases.json`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_submission.py -q`

## Task C4: Apply Idempotent Complete-Scope Enrichment

**Responsibility:** Revalidate under shared transaction, apply identical replay/complete replacement, and preserve deterministic sections.

**Acceptance criteria:** ME-AC6; under-lock identical replay succeeds before expected-revision comparison after unrelated scope updates; changed content with stale expected revision conflicts; only selected scope changes; persisted canonical input usage and final count/byte limits are enforced.

**Dependencies:** C3.

**Primary files:**

- `src/repo_dive/knowledge_map/enrichment_service.py`
- `tests/unit/knowledge_map/test_enrichment_service.py`
- `tests/integration/test_map_enrichment.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_enrichment_service.py tests/integration/test_map_enrichment.py -q`

## Task C5: Implement Scope Reset

**Responsibility:** Remove one scope's snapshot/records via shared transaction and preserve deterministic bytes/revision.

**Acceptance criteria:** reset enriched/evidence-ready/pending states behaves exactly as designed; unrelated scopes remain byte-equivalent.

**Dependencies:** C4.

**Primary files:**

- `src/repo_dive/knowledge_map/enrichment_service.py`
- `tests/unit/knowledge_map/test_enrichment_service.py`
- `tests/integration/test_map_reset.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/knowledge_map/test_enrichment_service.py tests/integration/test_map_reset.py -q`

### Checkpoint B

- [ ] C3-C5 focused tests pass.
- [ ] Complete-scope replacement and reset preserve deterministic section bytes.
- [ ] Validation messages do not claim entailment or semantic truth.

Rollback: disable replacement/reset services together; preserve prior valid artifacts.

## Task C6: Verify Semantic Contention, Security, And Bounds

**Responsibility:** Add cross-writer race, stale state, oversized input/artifact, path/reference abuse, recovery, and repeated-growth tests.

**Acceptance criteria:** ME-AC7/ME-AC8/ME-AC9; no successful update is lost; all errors preserve bytes and safe diagnostics.

**Dependencies:** C2-C5.

**Primary files:**

- `tests/integration/test_map_concurrency.py`
- `tests/integration/test_security.py`
- `tests/integration/test_recovery.py`
- `tests/performance/test_knowledge_map_budget.py`

**Verification:** `.venv/bin/python -m pytest tests/integration/test_map_concurrency.py tests/integration/test_security.py tests/integration/test_recovery.py tests/performance/test_knowledge_map_budget.py -q`

### Checkpoint C

- [ ] `.venv/bin/python -m pytest tests/unit/knowledge_map/test_evidence.py tests/unit/knowledge_map/test_evidence_service.py tests/unit/knowledge_map/test_submission.py tests/unit/knowledge_map/test_enrichment_service.py -q`
- [ ] Semantic integration/security/recovery/performance tests pass.
- [ ] `make check`

Rollback: semantic modules can be disabled while deterministic maps with empty arrays stay valid. Any store/model defect returns to Child 2 planning.

## Completion Gate

- [ ] ME-AC1 through ME-AC9 pass.
- [ ] Services are ready for thin CLI wiring.
- [ ] No CLI, Wiki, plugin, or product documentation file changed.
