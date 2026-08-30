# Knowledge Map Parent Integration Plan

## Parent Role

This parent task owns requirements, capability/dependency mapping, cross-child acceptance, and final integration review. It contains no direct product implementation and must remain `planning`; implementation starts with the first reviewed child only.

## Dependency Order

```text
1. 08-30-relationship-provenance-index-schema
   -> 2. 08-30-deterministic-knowledge-map
      -> 3. 08-30-map-evidence-enrichment
      -> 4. 08-30-map-cli-docs-evaluation

Child 4 starts only after both domain children complete, preserving strict 1 -> 2 -> 3 -> 4 handoff order.
```

## Parent Review Tasks

### P1: Freeze Cross-Child Public Contracts

**Acceptance criteria:**

- [ ] All children use only Knowledge Map / `repo-dive map` / `repo_dive.knowledge_map` / `.repo-dive/knowledge-map.json`.
- [ ] Budget object, artifact identity/revision, lock transaction, claim schema, command table, and error matrix match the parent design exactly.
- [ ] Every budget field has the approved derivation/capacity classification and every shared error applicability cell has an independent process test.
- [ ] Scope contracts and Evidence/enrichment projections are frozen before Child 3; idempotence order, canonical input usage, and error enum/precedence tests match the parent.
- [ ] No child introduces Wiki topics, `map status`, `repo-dive graph`, source-chunk nodes, a second lock protocol, or semantic completion gates.

**Verification:** Read every child PRD/design top to bottom and run `task.py validate` for all five tasks.

### P2: Review Child Dependency Handoffs

**Acceptance criteria:**

- [ ] Child 1 exports occurrence facts without map dependencies.
- [ ] Child 2 consumes Child 1 and owns the only map write transaction API.
- [ ] Child 3 consumes the frozen Child 2 models/store and does not edit lock ownership.
- [ ] Child 4 consumes domain services and keeps CLI thin.

**Verification:** Compare child likely-file ownership and explicit dependency sections; any overlap in store/model ownership returns to planning.

### Checkpoint P-A

- [ ] Parent and all children remain `planning`.
- [ ] Every child has `prd.md`, `design.md`, `implement.md`, and valid implement/check manifests.
- [ ] No product or published documentation file changed during planning.

### P3: Cross-Child Acceptance Review After Implementation

This task occurs only after all children independently pass their completion gates.

**Acceptance criteria:**

- [ ] KM-AC1 through KM-AC12 have an owning child result and concrete verification evidence.
- [ ] Relationship occurrence semantics survive through aggregation, flows, views, Evidence, and CLI output.
- [ ] Build/evidence/enrich/reset all use the same lock/revision transaction and preserve last valid bytes.
- [ ] Deterministic-only and enriched workflows both pass end to end.
- [ ] Existing index/retrieval/context/Wiki behavior remains compatible.

**Verification:**

```bash
make setup
make check
make test-unit
make test-all
git diff --check
```

Also validate the exact staged snapshot under `.trellis/spec/backend/tooling-integration-contracts.md` before completion.

### P4: Final Contract And Documentation Parity Review

**Acceptance criteria:**

- [ ] Executable help, command adapters, error codes, artifact schema, evaluations, and English/Chinese docs agree.
- [ ] Evaluation reports citation validity, referential integrity, freshness, reproducibility, and semantic usefulness separately.
- [ ] Wiki ownership remains unchanged and no independent comparison proposal was modified or presented as implementation authority.

**Verification:** repository contract checks plus manual field/heading parity review.

### Checkpoint P-B: Parent Completion

- [ ] All four children are completed and archived according to Trellis workflow.
- [ ] Full clean-environment validation is green.
- [ ] A separate full-scope code review reports no unresolved correctness, concurrency, provenance, budget, security, or compatibility finding.
- [ ] Parent can be archived without direct product-code commits of its own.

## Traceability

| Requirement | Acceptance | Primary child |
|---|---|---|
| KM-R1 | KM-AC1, KM-AC3 | Relationship provenance/index schema |
| KM-R2 | KM-AC2, KM-AC3 | Deterministic Knowledge Map |
| KM-R3 | KM-AC2, KM-AC3, KM-AC11 | Deterministic Knowledge Map |
| KM-R4 | KM-AC2, KM-AC4, KM-AC10 | Deterministic Knowledge Map |
| KM-R5 | KM-AC5, KM-AC10 | Deterministic Map; CLI/docs/evaluation |
| KM-R6 | KM-AC7 | Deterministic Map; Evidence/enrichment |
| KM-R7 | KM-AC8 | Deterministic Map transaction; all writer integration |
| KM-R8 | KM-AC4, KM-AC9 | Deterministic Map; CLI/docs/evaluation |
| KM-R9 | KM-AC6, KM-AC7 | Map Evidence/enrichment |
| KM-R10 | KM-AC9 | Map CLI/docs/evaluation |
| KM-R11 | KM-AC10, KM-AC11, KM-AC12 | Map CLI/docs/evaluation; parent final review |

## Rollback

If a child exposes a parent-contract defect, return that child and the parent to planning before implementation continues. Do not patch around a bad contract in a downstream child. Relationship Schema rollback is independent; deterministic package rollback retains the upgraded fact index; semantic rollback retains deterministic maps; CLI rollback removes public registration without deleting artifacts.
