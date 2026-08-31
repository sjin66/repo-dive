# Deterministic Knowledge Map Design

## Package Ownership

```text
repo_dive/knowledge_map/
  models.py       complete strict Schema 1.0 and budget/revision contracts
  store.py        strict read, advisory lock, MapWriteTransaction, atomic write
  snapshot.py     bounded published-index adapter and coverage
  resolution.py   conservative Python reference resolution
  lifting.py      repository/file/module/symbol projection and aggregates
  analysis.py     importance signals and rank
  topology.py     clusters, SCCs, layers
  flows.py        static flow candidates and reading tour
  build.py        deterministic lifecycle orchestration
  views.py        pure bounded projections
```

Downstream Evidence/enrichment modules may import these contracts. They cannot add another store/lock or write the artifact directly.

## Models And Identity

`models.py` implements the parent top-level artifact, revisions, source identity, strict budget object, coverage, four node kinds, fact edges, structures, deterministic scope contracts, and the complete Evidence/enrichment projections specified by the parent. Semantic arrays can initially be empty, but their strict nested field shapes, enums, canonical byte/hash metrics, and reference rules are frozen so Child 3 need not change the artifact schema.

Stable IDs use length-prefixed hashing. Parser symbol/relationship IDs remain explicit source references. File/module/cluster/flow/tour IDs derive only from normalized stable inputs. Collections validate their documented producer order and uniqueness.

`deterministic_revision` includes source/index identity, schema/algorithm versions, `source_fact_budget`, only the parent-classified derivation fields, and canonical deterministic sections. Semantic-capacity fields are persisted capacity limits but excluded from deterministic identity. `semantic_revision` includes snapshots/enrichments. `artifact_revision` increments on each changed write. `content_hash` excludes itself.

## Budget Semantics

The service receives a validated `MapBuildBudgets` assembled from the two top-level values and strict budget document. It classifies every field exactly as the parent derivation/semantic-capacity/artifact-capacity/operational table. Source-fact overflow fails because partial inventory would bias global analysis. Node/edge/cluster/flow/tour outputs may truncate only under explicit deterministic inclusion rules and complete omission metadata. Required endpoint closure or minimum repository/file structure fails rather than producing dangling output.

Changing semantic capacity preserves current snapshots/enrichments only when snapshot/reference/record/scope/claim/node/citation/input limits remain satisfied. A reduction below current usage returns `knowledge_map_capacity_conflict` without a write.

The artifact-byte budget is capacity-only. Every candidate is serialized exactly once for the final byte check.

## MapWriteTransaction

`store.py` owns:

```text
read_snapshot(repository) -> MapSnapshot
write_transaction(repository, expected_snapshot, current_index) -> context manager
```

The transaction acquires the transient advisory lock with a bounded wait, re-reads bytes, rechecks the published index and operation references, permits a pure operation callback to recognize exact current-intent equivalence, and otherwise compares `(artifact_revision, content_hash)` or an absent/invalid byte hash before accepting one fully validated candidate, enforcing capacity, and calling the existing atomic write primitive. The callback cannot merge or mutate; lock release is guaranteed.

Build may derive outside the lock. If a concurrent writer already produced the exact deterministic intent, build returns unchanged and preserves its semantics; otherwise baseline drift fails with revision conflict rather than merging. Read-only views load one complete snapshot and need no writer lock.

## Snapshot Adapter

The adapter paginates supported indexing reads with stable path/ID keys. It verifies manifest/database identity and source build identity, applies bounded named JSON/TOML manifest parsing consistent with repository-classification contracts, and records safe signal/observation IDs. It holds no terminal/filesystem-provider logic beyond the explicit index adapter.

## Resolution And Lifting

Resolution rules are the parent Python-only exact-to-conservative sequence. Ambiguity persists bounded candidates; no arbitrary winner is selected.

Lifting creates all essential repository/file/module nodes before selected symbols, maintains endpoint closure, and projects occurrence relationships to aggregate file/module edges. Each aggregate stores occurrence and unique-neighbor metrics separately, bounded contributor IDs, contributor total/truncation, confidence min/max, and derivation rule.

## Analysis And Topology

Importance uses unique fan-in/fan-out and explicit entrypoint/public API/docs/test/bridge signals. Repeated occurrences do not increase fan-in/out. Rank is lexicographic and persisted.

Clusters use package/directory boundaries and deterministic undersized merge. SCC uses Tarjan over unique module adjacency. Closed path signals classify layers; conflicting non-Test layers remain `unclassified`. Every rule/version/threshold is persisted.

## Flows And Tour

Flow traversal consumes unique adjacency but retains representative occurrence IDs for Evidence. Root and transition registries are closed as defined by the parent. Stable queue traversal, cycle avoidance, bounds, utility suppression, exact-sequence deduplication, no-prefix emission, terminal reasons, and static coverage are persisted.

Tour uses the parent category and rank tuples. One target appears once; adjacent items create `next_in_tour` derived edges.

After clusters, flows, and tour are final, build emits parent-defined cluster/flow/tour `scope_contracts` with exact allowed fact-node expansion, anchor IDs, record/claim permission tables, ordering, and contract hashes. These contracts are part of deterministic revision and are the sole semantic authorization input for Child 3.

## Build Transitions

- Absent -> current deterministic artifact, revision 1, empty semantic revision.
- Same deterministic/capacity input -> `unchanged`, no lock write.
- Same deterministic input and changed semantic/artifact capacity -> transaction preserves semantic sections only when every new limit and final byte capacity fits; otherwise no-write capacity error.
- Changed index/derivation -> transaction clears snapshots/enrichments and reports discarded counts.
- Invalid baseline -> may replace only if the post-lock invalid byte hash still equals the baseline sentinel.

Build never waits for semantic state.

## Views

`views.py` accepts a current validated artifact and explicit result limit from its caller. Architecture returns layers/clusters/modules/aggregate dependencies; flows returns bounded static flow records; tour returns bounded stops. All include `artifact_revision`, deterministic/semantic revisions, coverage, included/omitted counts, and semantic availability. Optional labels are presentation fields only.

## Compatibility And Rollback

The package is additive and unregistered publicly in this child. Rollback removes it without reverting the relationship Schema prerequisite. Repository artifacts are never deleted automatically. Wiki remains independent. No runtime graph dependency is added.
