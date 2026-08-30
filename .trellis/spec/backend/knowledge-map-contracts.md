# Knowledge Map Contracts

> Executable deterministic artifact, derivation, and writer contracts.

## Scenario: Deterministic Knowledge Map Schema 1.0

### 1. Scope / Trigger

- Apply this contract when changing `repo_dive.knowledge_map`, its supported index
  reads, `.repo-dive/knowledge-map.json`, or any downstream Evidence/enrichment writer.
- The deterministic map must remain useful with empty semantic sections.
- This layer owns the one shared map store and lock. Downstream features must not add
  another artifact writer, lock protocol, or deterministic fact origin.
- Public fact-node kinds are exactly `repository`, `module`, `file`, and `symbol`.
  Source Chunks are Evidence references, never fact nodes.

### 2. Signatures

```python
MapBuildBudgets.from_budget_document(
    document: object,
    *,
    source_fact_budget: int,
    artifact_byte_budget: int,
) -> MapBuildBudgets

KnowledgeMapArtifact.create(...) -> KnowledgeMapArtifact
KnowledgeMapArtifact.from_document(document: object) -> KnowledgeMapArtifact
KnowledgeMapArtifact.to_document() -> JsonObject

KnowledgeMapBuildService.build(
    repository: str | Path,
    *,
    budgets: MapBuildBudgets,
) -> MapBuildResult

MapStore(repository).read_snapshot() -> MapSnapshot
MapStore(repository).read_artifact() -> KnowledgeMapArtifact
MapStore(repository).write_transaction(
    expected_snapshot: MapSnapshot,
    *,
    lock_timeout: float = 2.0,
    revalidate: Callable[[], None] | None = None,
) -> MapWriteTransaction

MapWriteTransaction.commit(
    candidate: KnowledgeMapArtifact,
    *,
    equivalent: Callable[[KnowledgeMapArtifact], bool] | None = None,
) -> MapWriteResult

project_architecture(artifact, *, max_results: int) -> JsonObject
project_flows(artifact, *, max_results: int) -> JsonObject
project_tour(artifact, *, max_results: int) -> JsonObject
```

### 3. Contracts

The top-level artifact contains exactly:

```text
schema_version, algorithm_id, algorithm_version, artifact_revision,
content_hash, deterministic_revision, semantic_revision, source,
derivation_parameters, capacity_limits, coverage, nodes, edges,
cycle_groups, clusters, layers, flows, tour, scope_contracts,
evidence_snapshots, enrichments
```

- Values are frozen dataclasses decoded with exact field sets. Paths are normalized
  repository-relative POSIX paths; line ranges are one-based and inclusive.
- IDs and producer order are deterministic. Every parent, endpoint, member, edge,
  candidate, scope, anchor, Evidence, and enrichment reference must close over the
  same artifact.
- `content_hash` hashes canonical content without itself.
  `deterministic_revision` binds source/index identity, algorithm identity,
  derivation parameters, deterministic sections, and scope contracts.
  `semantic_revision` binds ordered Evidence snapshots and enrichments.
- Derivation budgets are `source_fact_budget`, node/edge/contributor/resolution/
  cluster/flow/tour limits. Changing one may change deterministic identity.
- Capacity limits are `artifact_byte_budget` and all Evidence/enrichment count,
  reference, claim, and canonical-input limits. Capacity changes preserve semantics
  only when every persisted value still fits; otherwise no write occurs.
- Index reads use supported stable paging and verify Manifest/database membership,
  counts, and content-addressed identities. Source-fact overflow fails rather than
  publishing a biased partial inventory.
- Aggregate dependencies preserve occurrence totals separately from unique-neighbor
  counts and bounded contributor IDs. Resolution ambiguity remains explicit.
- Importance signals are labeled raw values with a persisted lexicographic rank.
  Clusters, SCC cycle groups, layers, flows, tour, and scope contracts are persisted
  deterministic projections, not recomputed presentation guesses.
- The writer sequence is: acquire bounded advisory lock, reload bytes, revalidate the
  current index/references, test exact intent equivalence, compare CAS identity,
  validate revision/content/capacity, serialize once, and atomically replace.
- A byte-equivalent deterministic build performs no write. Derivation/index changes
  clear semantic sections; compliant capacity-only changes preserve them.
- Views read one validated artifact, require positive `max_results`, return explicit
  included/omitted/truncated metadata, and may merge presentation labels only.

### 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Unknown/missing field, duplicate JSON key, non-standard constant | Reject as `knowledge_map_invalid` or domain validation failure |
| Unsupported schema/algorithm, hash/revision drift, dangling or misordered reference | Reject without rewriting artifact bytes |
| Missing artifact | `knowledge_map_not_found` |
| Source facts exceed required budget | `knowledge_map_source_budget_exceeded`; no artifact write |
| Required node/edge closure cannot fit | `knowledge_map_budget_exceeded`; no artifact write |
| Writer lock exceeds bounded timeout | `knowledge_map_locked`; preserve previous bytes |
| Published index changes under lock | `knowledge_map_index_changed`; preserve previous bytes |
| Exact current intent already exists | Return `changed=False` before CAS conflict handling |
| Non-equivalent current CAS identity differs | `knowledge_map_revision_conflict` |
| Candidate is not the next positive revision | `knowledge_map_validation_failed` |
| Current semantic usage exceeds requested capacity | `knowledge_map_capacity_conflict`; no silent truncation |
| Serialized candidate exceeds artifact bytes | `knowledge_map_artifact_budget_exceeded` |
| Atomic replacement fails | `knowledge_map_write_failed`; previous bytes remain valid |
| View `max_results <= 0` | `ValueError` before projection |

### 5. Good/Base/Bad Cases

- Good: two identical builds over one published index preserve exact artifact bytes,
  revisions, and semantic sections on the second run.
- Good: a capacity increase writes the next artifact revision while preserving
  compliant Evidence/enrichment content and deterministic revision.
- Base: an unenriched repository builds a valid architecture/flows/tour artifact with
  empty `evidence_snapshots` and `enrichments`.
- Bad: applying raw occurrence counts as centrality inflates importance for repeated
  calls; use unique neighbors and retain occurrence totals separately.
- Bad: checking a revision before acquiring the lock, or checking CAS before exact
  equivalence, creates lost updates or rejects an already-applied intent.
- Bad: reducing a semantic limit by dropping records silently violates reproducibility;
  return `knowledge_map_capacity_conflict` without mutation.

### 6. Tests Required

- Model tests assert exact field closure, immutable nested values, canonical byte
  stability, all three hashes, producer ordering, hierarchy/reference closure, strict
  scope permissions, and frozen Evidence/enrichment round trips.
- Store/concurrency tests assert POSIX process contention, bounded timeout, lock release
  after revalidation errors, equivalence-before-CAS, absent/invalid/current races,
  atomic failure preservation, and portable Windows lock branches.
- Snapshot tests assert stable paging, count/membership/content-ID validation, source
  budget failure, actual UTF-8 manifest limits, and no source-text audit leakage.
- Fixture tests cover exact/relative/alias/unique/ambiguous/unresolved resolution,
  endpoint-closed lifting, aggregate metrics, package clustering, max-connectivity
  merging, SCCs, layers, flow/tour ties, cycles, suppression, and truncation.
- Lifecycle tests assert deterministic no-op, index/derivation invalidation, every
  semantic-capacity usage dimension, artifact capacity, concurrent semantic
  preservation, and no-write failure paths.
- View tests assert referential output, positive result bounds, accurate truncation,
  optional labels without fact mutation, and no Wiki or Agent fact edges.
- `make check`, all performance tests, executable Knowledge Map evaluation cases, and
  `make test-all` must pass from the exact staged clean snapshot.

### 7. Wrong vs Correct

#### Wrong

```python
current = store.read_artifact()
if current.artifact_revision == expected_revision:
    atomic_write_bytes(repository, MAP_ARTIFACT_PATH, candidate_bytes)
```

#### Correct

```python
baseline = store.read_snapshot()
with store.write_transaction(baseline, revalidate=recheck_index) as transaction:
    result = transaction.commit(candidate, equivalent=is_exact_current_intent)
```

The correct form places revalidation, equivalence, CAS, validation, byte capacity, and
atomic replacement under the one shared bounded writer lock.
