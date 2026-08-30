# Map Evidence And Enrichment

## Goal

Add optional scope-owned Evidence and claim-level Agent semantics to a current deterministic Knowledge Map without changing parser/derived facts, requiring semantic completion, or introducing a second persistence/lock protocol.

## Dependencies

- Requires `08-30-deterministic-knowledge-map` models, build lifecycle, and `MapWriteTransaction` to be complete and frozen.
- Must not modify the lock/store ownership contract; an inadequate shared transaction returns this task to planning.
- Exports Evidence, enrichment, reset, and validation services to `08-30-map-cli-docs-evaluation`.
- Owns KM-R9 and semantic portions of KM-R6/KM-R7/KM-R8.

## Requirements

### ME-R1 Scope Evidence Planning

- Supported scopes are existing cluster, flow, or tour IDs from the current deterministic revision.
- Allowed facts, required anchors, and record/claim kinds come only from the persisted closed scope contract; Child 3 cannot widen them.
- Build a deterministic query/anchor plan with mandatory direct complete chunks before supplemental retrieval.
- Every collection requires a positive token budget; required Evidence that cannot fit returns repository/requested-data exit `3` and persists nothing.
- Snapshot count and Evidence references per snapshot obey persisted capacities; required reference overflow returns repository/requested-data exit `3` without partial persistence.
- Snapshot identity binds scope, deterministic revision, index build/fingerprint, query/parameters, token accounting, ordered references, and content hash.

### ME-R2 Snapshot Lifecycle

- Each scope owns at most one current Evidence snapshot.
- Equivalent recollection is idempotent and byte-preserving.
- A different uncited snapshot may replace the prior snapshot through the shared revision-checked transaction.
- A different cited snapshot returns a conflict; `map reset --scope` is the explicit recovery path.
- Stale map/index/Evidence, unknown scope, lock timeout, revision conflict, and write failure preserve previous bytes.

### ME-R3 Claim-Level Submission

- One strict input replaces the complete enrichment record set for exactly one scope and includes `expected_artifact_revision`.
- Record kinds and claim kinds are closed. Every label, summary, responsibility, flow explanation, concept description, reading guidance statement, and association is an individual claim.
- Each claim has non-empty bounded `text`, `fact_node_ids`, and `evidence_ids`; record-level catch-all citations do not exist.
- Canonical input usage excludes `expected_artifact_revision`, is persisted per scope as bytes/hash, and is independently reproducible for capacity checks.
- References must exist, be allowed by the scope contract, belong to its current snapshot, and remain fresh.

### ME-R4 Fact And Semantic Separation

- Agent input cannot supply origin, confidence, parser/derived node/edge/cluster/layer/flow/tour fields, lifecycle state, or artifact revisions other than the expected revision.
- Agent associations stay inside semantic records and never project into fact edges.
- Validation proves schema, citation validity/ownership, referential integrity, and Evidence freshness, not natural-language entailment or truth.

### ME-R5 Idempotence, Replacement, Reset, And Bounds

- Identical complete-scope replay succeeds unchanged.
- Under-lock identical replay is detected before expected-revision equality, so an unrelated scope update does not break idempotence.
- Different valid complete-scope content replaces only that scope when expected revision matches under the shared lock.
- Reset removes only one scope's snapshot/enrichment, preserves deterministic bytes/revision, increments artifact revision, and recomputes semantic revision.
- Enforce persisted snapshot, Evidence-references-per-snapshot, record, records-per-scope, claims, fact/related-node references, citations, input-byte, and final-artifact-byte limits before write.
- Repeated calls cannot grow the artifact beyond limits.
- The shared exact-equivalence hook may return unchanged only after current index/Evidence/reference validation and never merges differing scope content.

## Acceptance Criteria

- **ME-AC1:** Exact scope expansion, permissions, representative anchors, Evidence planning, IDs, and tie order are deterministic; mandatory direct chunks precede supplemental chunks.
- **ME-AC2:** Insufficient required token budget is exit `3`, writes nothing, and reports required/provided tokens without source text.
- **ME-AC3:** Snapshot persistence is scope-owned, current, idempotent, bounded, and cannot orphan citations.
- **ME-AC4:** Every accepted Agent label, association, or semantic statement has its own valid fact-node and Evidence references; record-level citation ambiguity is impossible.
- **ME-AC5:** Malformed schema/claim input is invocation exit `2`; unknown/stale/wrong-scope repository references are exit `3`; all failures preserve bytes.
- **ME-AC6:** Identical replay after an unrelated revision advance is unchanged; revision-checked different complete-scope replacement updates only that scope; reset returns it to pending.
- **ME-AC7:** Build/evidence/enrich/reset contention cannot lose updates because all use the same shared transaction.
- **ME-AC8:** Validation explicitly reports referential/freshness status without claiming semantic entailment.
- **ME-AC9:** Focused semantic, concurrency, security, recovery, and budget tests plus `make check` pass.

## Out Of Scope

- Deterministic graph derivation or changes to map model/store/lock/build ownership.
- CLI registration, product documentation, Wiki semantics, Wiki Evidence reuse, or implicit Agent/model calls.
- Automated semantic truth scoring or “100% grounding precision” claims.
- Partial record merges, append-only semantics, or cross-scope Agent relationships.

## Open Questions

None.
