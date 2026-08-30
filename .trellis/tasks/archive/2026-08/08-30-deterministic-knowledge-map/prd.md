# Deterministic Knowledge Map

## Goal

Build the complete deterministic, bounded, versioned Knowledge Map and shared writer transaction so architecture, static-flow, and reading-tour views work without Agent enrichment.

## Dependencies

- Requires `08-30-relationship-provenance-index-schema` to complete.
- Exports frozen map models, store/lock/revision transaction, deterministic build service, and read projections to both downstream children.
- Owns KM-R2 through KM-R8 except Agent-specific validation and public command integration.

## Requirements

### DM-R1 Strict Artifact Contract

- Define strict immutable Schema 1.0 values for source identity, budgets, coverage, repository/module/file/symbol nodes, parser/derived edges, clusters, layers, flows, tour, exact scope contracts, complete Evidence/enrichment projections, revisions, and hashes.
- Reject unknown fields, duplicate IDs, invalid paths/ranges/confidence, dangling references, unsupported versions, inconsistent ordering/counts, and hash/revision drift.
- Public graph nodes exclude source chunks; chunks appear only in Evidence references.

### DM-R2 Shared Writer Transaction

- Own one repository-local bounded advisory lock and one `MapWriteTransaction` for all build/evidence/enrich/reset writes.
- After lock acquisition, reload and revalidate index/references, recognize only exact current-intent equivalence, and otherwise compare expected revision/content hash before validating/serializing/size-checking and atomically replacing the candidate.
- Expose stable lock timeout, revision conflict, index-change, validation, and write errors.
- Preserve previous bytes for every failure.

### DM-R3 Bounded Published-Index Snapshot

- Read immutable facts through supported indexing interfaces in stable pages/order under explicit source-fact budget.
- Apply registered bounded classification/manifest signals where needed and persist safe coverage/observation metadata.
- Never mutate SQLite, inspect ignored files, execute repository code, or leak source text into audit metadata.

### DM-R4 Resolution And Lifting

- Resolve only supported Python qualified references conservatively and preserve ambiguity/unresolved coverage.
- Create deterministic repository/file/module/symbol nodes and aggregate occurrence relationships upward.
- Preserve unique-neighbor and occurrence metrics, confidence bounds, bounded contributing IDs, endpoint closure, and explicit omission reasons.

### DM-R5 Explainable Analysis

- Persist raw importance signals and a documented stable rank tuple.
- Form deterministic package/directory clusters, SCC cycle groups, closed architecture layers, and `unclassified` fallback.
- Every heuristic includes a fixture/evaluation case.

### DM-R6 Static Flows And Tour

- Use the parent closed roots, edge set, traversal order, utility rule, budgets, deduplication, and terminal reasons.
- Label import fallback and incomplete parser coverage; never claim guaranteed runtime behavior.
- Produce deterministic tour order and adjacency without Agent control.

### DM-R7 Build Lifecycle

- Publish a valid deterministic map with empty semantic state.
- Same deterministic input is a no-op preserving semantics/revisions.
- Semantic-capacity changes preserve compliant current semantics and leave deterministic revision unchanged; reductions below current usage fail without mutation.
- Index/derivation changes clear semantic state; semantic/artifact capacity changes preserve only content that satisfies every new limit.
- Invalid/stale baseline replacement and concurrent changes follow the parent lock/CAS protocol.

### DM-R8 Pure Views

- Produce bounded architecture, flows, and tour projections from one complete current artifact snapshot.
- Views reference only persisted IDs, merge optional labels without changing facts, require caller result bounds at the later CLI boundary, and never mutate state.
- No `status`, Wiki topic, Markdown authority, or public command registration is added in this child.

## Acceptance Criteria

- **DM-AC1:** Strict artifact, scope-contract, Evidence, and enrichment model round-trips are canonical, byte-stable, timestamp-free, and reject every invalid identity/reference/order/hash case.
- **DM-AC2:** Contested write transactions cannot lose updates; lock/revision/index/write failures preserve exact previous bytes.
- **DM-AC3:** Snapshot paging is stable, bounded, read-only, and reports complete language/parser/relationship coverage.
- **DM-AC4:** Resolution/lifting fixtures preserve traceability, ambiguity, occurrence counts, unique-neighbor counts, and endpoint closure.
- **DM-AC5:** Importance, clusters, SCCs, layers, flows, and tour match pinned deterministic fixtures/evaluations under ties, cycles, sparse facts, and truncation.
- **DM-AC6:** Deterministic-only `build -> validate-domain -> project` succeeds with empty semantic arrays.
- **DM-AC7:** Identical build is byte-preserving; index/derivation changes clear semantics; semantic/artifact capacity changes preserve compliant content and reject reductions below current usage.
- **DM-AC8:** Architecture/flow/tour projections are bounded, referentially valid, read-only, and contain no Wiki topics or Agent fact edges.
- **DM-AC9:** Focused unit/integration/performance tests and `make check` pass.

## Out Of Scope

- Agent Evidence retrieval, claim submission validation, or semantic service mutation.
- CLI registration, process envelopes, bilingual product docs, or final full-suite evaluation integration.
- Wiki changes, source-chunk nodes, JS/TS relationship expansion, graph databases, or implicit models.

## Open Questions

None.
