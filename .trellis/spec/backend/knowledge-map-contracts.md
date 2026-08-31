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
| Persisted Evidence references no longer match the current index | `knowledge_map_evidence_stale`; preserve artifact bytes |
| Missing artifact | `knowledge_map_not_found` |
| Source facts exceed required budget | `knowledge_map_source_budget_exceeded`; no artifact write |
| Required node/edge closure cannot fit | `knowledge_map_budget_exceeded`; no artifact write |
| Writer lock exceeds bounded timeout | `knowledge_map_locked`; preserve previous bytes |
| Published index changes under lock | `knowledge_map_index_changed`; preserve previous bytes |
| Exact current intent already exists | Return `changed=False` before CAS conflict handling |
| Non-equivalent current CAS identity differs | `knowledge_map_revision_conflict` |
| Writer candidate is not the next positive revision | `knowledge_map_validation_failed`; this is not a read-time `map validate` classification |
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

## Scenario: Scope Evidence And Claim Enrichment

### 1. Scope / Trigger

- Apply this contract when collecting Knowledge Map Evidence, decoding Agent-owned
  claims, replacing one scope's semantic records, resetting semantics, or reporting
  semantic validation health.
- Supported scopes and permissions come only from persisted cluster, flow, and tour
  `ScopeContract` values. Semantic services may not widen deterministic facts or add
  fact edges, another writer, or another lock.

### 2. Signatures

```python
plan_scope_evidence(
    artifact: KnowledgeMapArtifact,
    scope_id: str,
    *,
    chunks: tuple[Chunk, ...],
    symbols: tuple[Symbol, ...],
    retrieval_parameters: RetrievalParameters,
) -> ScopeEvidencePlan

KnowledgeMapEvidenceService.collect(
    repository: str | Path,
    *,
    scope_id: str,
    token_budget: int,
) -> ScopeEvidenceResult

decode_enrichment_submission(payload: bytes) -> EnrichmentSubmission

KnowledgeMapEnrichmentService.enrich(
    repository: str | Path,
    *,
    payload: bytes,
) -> EnrichmentResult

KnowledgeMapEnrichmentService.reset(
    repository: str | Path,
    *,
    scope_id: str,
) -> EnrichmentResult

KnowledgeMapEnrichmentService.validate(
    repository: str | Path,
) -> SemanticValidationResult
```

### 3. Contracts

- Evidence planning selects complete mandatory chunks in persisted anchor order.
  Symbol anchors use their definition chunk; file/module fallback order is
  `(path, start_line, end_line, symbol_kind_order, qualified_name, symbol_id,
  chunk_id)`, then complete file chunks by `(path, start_line, end_line, chunk_id)`.
  Duplicate chunks retain first occurrence and collect all mapped anchor IDs.
- Mandatory references are preflight-packed before supplemental search. They reserve
  tokens and reference capacity, always precede supplemental Evidence, and failure
  performs neither retrieval nor artifact mutation.
- Before recollection, any existing snapshot is freshness-validated even when it is
  uncited. Equivalent recollection preserves bytes; a changed uncited snapshot may be
  replaced; a changed cited snapshot requires reset.
- Enrichment input is exactly one strict UTF-8 JSON object with fields
  `schema_version`, `scope_id`, `expected_artifact_revision`, and `records`.
  Records contain only `id`, `kind`, and `claims`; every claim independently owns
  `kind`, `text`, `fact_node_ids`, `related_node_ids`, and `evidence_ids`.
- Submission decoding rejects duplicate keys, non-standard constants, unknown or
  missing fields, padded/duplicate IDs, empty required reference arrays, and input
  above the fixed reader ceiling. Persisted capacities additionally bound raw and
  canonical input bytes, records, claims, references, and final artifact bytes.
- Enrichment is complete-scope replacement. Under the shared lock, current Evidence
  and references are revalidated and exact scope-content equivalence is tested before
  expected artifact revision. Different content requires an exact current revision
  and changes only the selected scope.
- Reset removes one scope's snapshot and enrichment, preserves deterministic revision
  and deterministic sections, and is unchanged when that scope is already pending.
- Semantic validation reports schema, reference integrity, scope ownership, and
  Evidence freshness. `semantic_entailment_checked` remains `False`.

### 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Non-positive operation token budget | Raise `ValueError` before index/retrieval work |
| Mandatory tokens do not fit | `knowledge_map_evidence_budget_insufficient`; report numeric required/provided values; no search or write |
| Snapshot/reference capacity cannot fit mandatory state | `knowledge_map_evidence_capacity_exceeded`; no partial snapshot |
| Existing snapshot contains stale Chunk identity/hash/location | Reject as stale repository Evidence before replacement; preserve bytes |
| Changed snapshot is cited by current enrichment | `knowledge_map_evidence_conflict`; recovery is scope reset |
| Invalid UTF-8/JSON/schema/shape/kind or duplicate key | `knowledge_map_enrichment_invalid` invocation error; preserve bytes |
| Missing/wrong-scope/stale node, Evidence, or scope reference | Repository error with recovery action; preserve bytes |
| Exact submitted scope content already exists | Return `changed=False` before expected-revision comparison |
| Different scope content has stale expected revision | `knowledge_map_revision_conflict`; preserve bytes |
| Current or candidate semantic capacity is exceeded | Capacity error; never truncate accepted claims or records |
| Reset of an already pending current scope | Return `changed=False` and preserve bytes |

### 5. Good/Base/Bad Cases

- Good: collect preflights all mandatory complete chunks, then appends bounded
  supplemental hits; an equivalent recollection leaves artifact bytes unchanged.
- Good: replay identical claims after another scope advances the artifact revision;
  equivalence wins under the lock and the replay remains unchanged.
- Base: a valid scope has no snapshot or enrichment; validation reports zero checked
  claims and does not imply semantic truth.
- Bad: search first and discover afterward that required chunks do not fit; this spends
  retrieval work and breaks the required-Evidence failure boundary.
- Bad: replace an uncited snapshot without validating its old references; staleness
  must not be silently healed by recollection.

### 6. Tests Required

- Pure planning tests pin cluster/flow/tour expansion, symbol/file/module fallback,
  tie ordering, chunk deduplication, anchor accumulation, and stable query-plan hashes.
- Collection tests assert mandatory preflight before search, direct-before-
  supplemental order, numeric budget errors, count limits, stale old-snapshot
  rejection, equivalent bytes, uncited replacement, and cited conflict.
- Decoder tests cover UTF-8, JSON closure, duplicate keys, constants, schema/kind
  closure, padded/duplicate values, required per-claim citations, and reader ceiling.
- Lifecycle tests cover replay after unrelated revisions, stale different-content
  conflicts, selected-scope replacement, reset isolation/pending no-op, semantic
  revision changes, freshness, and no entailment claim.
- Shared writer tests cover real process contention, lock timeout/release, index races,
  artifact-byte overflow, atomic replacement failure, and prior-byte preservation.
- Public validation tests distinguish strict artifact decode failures
  (`knowledge_map_invalid`) from current-index Evidence freshness failures
  (`knowledge_map_evidence_stale`). Candidate revision failures remain covered at
  `MapWriteTransaction.commit()` rather than synthesized through `map validate`.

### 7. Wrong vs Correct

#### Wrong

```python
search = search_repository(repository, plan.query)
bundle = pack(search.hits, mandatory=mandatory, token_budget=token_budget)
replace_snapshot_without_validating(existing)
```

#### Correct

```python
validate_existing_snapshot_freshness(existing)
pack((), mandatory=mandatory, token_budget=token_budget)  # preflight
search = search_repository(repository, plan.query)
bundle = pack(search.hits, mandatory=mandatory, token_budget=token_budget)
with store.write_transaction(baseline, revalidate=recheck_index) as transaction:
    transaction.commit(candidate, equivalent=validate_then_compare_scope_intent)
```

The correct order prevents retrieval on required-capacity failure, refuses to conceal
stale persisted Evidence, and keeps equivalence, revision checks, and mutation inside
the one shared writer protocol.

## Scenario: Public Knowledge Map Commands

### 1. Scope / Trigger

- Apply this contract when registering, changing, documenting, or process-testing the
  public Knowledge Map command family.
- The public name is only `repo-dive map`; the command adapter owns arguments,
  bounded input, output projection, and error-envelope integration, not derivation,
  semantics, persistence, locking, or model invocation.

### 2. Signatures

```text
repo-dive map build <repository>
  --source-fact-budget <count>
  --artifact-byte-budget <bytes>
  --budget-file <repository-relative-path>
  [--format json]

repo-dive map show <repository>
  --view architecture|flows|tour --max-results <count> [--format json]

repo-dive map evidence <repository>
  --scope <scope-id> --token-budget <tokens> [--format json]

repo-dive map enrich <repository>
  --input <repository-relative-path|-> [--format json]

repo-dive map reset <repository>
  --scope <scope-id> [--format json]

repo-dive map validate <repository> [--format json]
```

### 3. Contracts

- The subcommand set is exactly `build`, `show`, `evidence`, `enrich`, `reset`, and
  `validate`. There is no `graph`, `status`, `init`, `unit`, Wiki-topic, package, or
  artifact alias.
- Every command is non-interactive and JSON-only. Success and failure each write one
  Schema 1.0 envelope document to stdout; diagnostics use stderr; JSON output contains
  no ANSI. The command field is `map build`, `map show`, and so on.
- Map-only envelope and recovery behavior is selected by the exact `map` command token,
  not a string prefix; unrelated names such as `maple` retain the non-Map CLI contract.
- Build budgets are positive and combine two required top-level values with a strict
  UTF-8 JSON budget document of at most 1,000,000 bytes. The budget file is confined
  beneath the selected repository and rejects duplicate keys, non-standard constants,
  unknown fields, malformed encoding, and non-object roots.
- `show` always has an explicit result bound. `evidence` always has a positive token
  bound. Enrichment input is repository-confined or `-` for stdin and is read only to
  `ENRICHMENT_READER_CEILING + 1` before the strict domain decoder rejects overflow.
- `show` and `validate` are read-only. Build, Evidence, enrichment, and reset publish
  only through the shared map transaction; repeated equivalent intent returns
  `changed=false`, `unchanged=true`, and preserves artifact bytes.
- Evidence output may return complete source Chunk text to the caller, but errors and
  diagnostics never disclose source text, escaped input targets, or host absolute
  paths. Error details contain bounded IDs/counts and machine recovery fields only.
- Map validation reports schema/reference/scope/freshness checks and always states
  `semantic_entailment_checked=false`; citation validity is not semantic truth.

### 4. Validation & Error Matrix

| Condition | Public process behavior |
|---|---|
| Missing/invalid flag or budget document | Exit `2`; invocation error; `correct_invocation` / `after_recovery` |
| Malformed enrichment UTF-8/JSON/schema/claim | Exit `2`; `knowledge_map_enrichment_invalid`; never generic `invalid_invocation` |
| Missing/confined input or repository state | Exit `3`; preserve map bytes; return the domain recovery action |
| Missing/stale/invalid map or Evidence/reference | Exit `3`; preserve bytes; require rebuild, recollection, reset, or corrected scope as applicable |
| Source, derivation, semantic, or artifact capacity failure | Exit `3`; report bounded required/provided or named-limit details; never truncate required state |
| Lock timeout, index change, or revision conflict | Exit `3`; no automatic retry/merge; preserve bytes |
| Unexpected derivation or atomic write failure | Exit `4`; safe diagnostic only; preserve last valid bytes |
| Exact build/Evidence/enrichment/reset replay | Exit `0`; one success document; no artifact write |

For every non-success Map domain error, `error.details.retry_mode` is one of
`unchanged`, `after_reload`, `after_recovery`, or `after_cause_clears`, and
`error.details.recovery_action` is the domain-defined closed action. Existing domain
details are retained when both fields already exist; the CLI adds only the established
mapping for errors that do not provide them.

### 5. Good/Base/Bad Cases

- Good: build twice over one current index and exact budgets; the second command is an
  unchanged success and the artifact bytes are identical.
- Good: collect Evidence, submit independently cited claims through stdin, validate,
  reset the scope, and retain one valid JSON document and stable recovery metadata at
  every step.
- Base: build and show a deterministic map with no semantic records; Wiki state and
  commands remain independent and unchanged.
- Bad: expose a domain exception through a generic process error, include an absolute
  escaped path in details, or treat domain-only tests as proof of the public envelope.
- Bad: add `map status`, silently default a required budget, retry a revision conflict,
  or infer semantic truth from citation presence.

### 6. Tests Required

- Help tests assert the exact six-command set, exact required flags and choices, and
  absence of forbidden aliases.
- Parser tests assert prefix-similar non-Map names do not gain Map-only JSON or recovery
  behavior, including when they independently request `--format json`.
- Every success path asserts one parseable JSON document, command/schema fields,
  stdout/stderr separation, no ANSI, explicit bounds, and stable result projection.
- Every checked command/error applicability cell has an independent process case that
  asserts stable code, exit, one error document, safe stderr, no ANSI, exact
  `retry_mode`/`recovery_action`, precedence, and map bytes before/after.
- Input tests cover repository traversal, symlink and absolute escape, missing paths,
  stdin, invalid UTF-8, duplicate keys, constants, oversized documents, and private
  source/path non-disclosure.
- Workflow tests cover deterministic-only build/show/validate, Evidence/enrich/
  validate/reset, exact replay, stale state, contention, no lost updates, and read-only
  commands. Compatibility tests keep index/search/context/retrieval/Wiki green.
- Evaluation tests keep citation validity, referential integrity, Evidence freshness,
  deterministic reproducibility, coverage/truncation, and explicit manual semantic
  usefulness as separate dimensions. English/Chinese docs must match executable help.

### 7. Wrong vs Correct

#### Wrong

```python
try:
    service.build(repository, budgets=budgets)
except Exception as error:
    print(error)  # leaks implementation/path details and bypasses the envelope
```

#### Correct

```python
try:
    result = service.build(repository, budgets=budgets)
except RepoDiveError:
    raise
except Exception as error:
    raise InternalOperationError(
        "knowledge_map_derivation_failed",
        "Knowledge Map derivation failed.",
        details={
            "retry_mode": "after_cause_clears",
            "recovery_action": "inspect_safe_diagnostic",
        },
    ) from error
```

The correct adapter preserves typed domain failures, translates only unexpected
operation failures, and leaves the root CLI responsible for one safe process envelope.
