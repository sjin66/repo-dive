# Knowledge Map Refactor Design

## 1. Authority And Scope

This is the canonical cross-child design. The independent `docs/superpowers` Knowledge Graph drafts are comparison material only and remain unchanged.

Canonical names are `repo-dive map`, `repo_dive.knowledge_map`, and `.repo-dive/knowledge-map.json`. The internal parser/index structure is the deterministic fact graph. Version 1 has no Wiki projection or dependency.

```text
published index
  -> exact parser occurrences
  -> deterministic fact graph
  -> file/module lifting and deterministic analysis
  -> .repo-dive/knowledge-map.json
  -> architecture / static flows / reading tour

optional per scope:
  deterministic scope -> Evidence snapshot -> Agent claims -> validated enrichment
```

## 2. Child Architecture

```text
relationship-provenance-index-schema
  -> deterministic-knowledge-map
       -> map-evidence-enrichment
            -> map-cli-docs-evaluation
```

| Child | Owns | Must not own |
|---|---|---|
| Relationship provenance | Parser occurrence model, SQLite Schema bump, manifest compatibility, graph/retrieval compatibility | Knowledge Map artifact or commands |
| Deterministic map | `repo_dive.knowledge_map` models, reader adapter, shared store/lock/revision transaction, derivation, build, projections | Agent claim decoding, CLI registration, Wiki |
| Evidence/enrichment | Evidence planning/snapshots, claim schema/validation, semantic mutation via shared transaction | A second lock/store protocol, deterministic facts, CLI registration, Wiki |
| CLI/docs/evaluation | `commands/map.py`, CLI wiring, full error integration, security/recovery/performance/evaluation, matched docs | Domain derivation or semantic ownership |

The parent has no product-code tasks. Completion requires all children plus a final cross-child review.

## 3. Relationship Occurrence Contract

Each parser syntax occurrence becomes one `Relationship`:

```text
id
source_id
target_id
kind
confidence
provenance
path
start_line
end_line
occurrence_discriminator
```

The ID hashes all semantic fields plus an occurrence discriminator derived from parser source order/column span. This distinguishes two calls to the same target on one line without exposing an unstable database row ID. Public Evidence requires POSIX path and one-based inclusive lines; the parser may retain column/byte positions solely to derive the discriminator.

Parser normalization deduplicates only identical occurrence IDs. Persistence uses relationship ID as the primary identity and validates `relationship.path == owning file_path`.

Three counting semantics are distinct:

| Consumer | Semantics |
|---|---|
| Graph traversal | One adjacency per `(source_id, target_id, kind)`; confidence/provenance representative chosen by a fixed stable rule |
| Importance fan-in/fan-out | Unique neighboring node count; repeated calls do not inflate centrality |
| Aggregate file/module edge | `occurrence_count` across all contributing occurrences plus bounded ordered IDs |

Structural retrieval keeps its current reachability, path scoring, stable tie-breakers, and result ordering. Occurrence storage must not multiply traversal paths or silently change scores. Any intended ranking change needs a separate evaluation-backed contract.

The parser version and SQLite Schema version increment together. Existing old indexes are rejected by consumers and rebuilt through the supported index flow; no in-place migration is added.

## 4. Public Knowledge Map Contract

### 4.1 Top-Level Identity

```json
{
  "schema_version": "1.0",
  "algorithm_id": "builtin-knowledge-map",
  "algorithm_version": "1",
  "artifact_revision": 1,
  "content_hash": "sha256:...",
  "deterministic_revision": "sha256:...",
  "semantic_revision": "sha256:...",
  "source": {},
  "derivation_parameters": {},
  "capacity_limits": {},
  "coverage": {},
  "nodes": [],
  "edges": [],
  "clusters": [],
  "layers": [],
  "flows": [],
  "tour": [],
  "scope_contracts": [],
  "evidence_snapshots": [],
  "enrichments": []
}
```

- `artifact_revision` is a positive monotonic integer incremented on every successful byte-changing write.
- `content_hash` hashes the canonical document with the `content_hash` field omitted.
- `deterministic_revision` hashes source/index identity, map schema/algorithm, all derivation parameters, and deterministic sections.
- `semantic_revision` hashes ordered Evidence snapshots and enrichments.
- A byte-equivalent replay performs no write and changes no revision.
- Wall-clock timestamps and lock metadata are absent from deterministic identity.

### 4.2 Public Nodes And Chunks

Public node kinds are `repository`, `module`, `file`, and `symbol`. There is no `source_chunk` node in Schema 1.0.

Chunks have no graph-query consumer that cannot be served by an `EvidenceRef`. Copying all chunks would duplicate source identity and consume artifact budget. A snapshot therefore references existing chunk ID, content hash, POSIX path, line range, role, and scope; source text is returned by `map evidence` but need not be duplicated as a graph node.

### 4.3 Edges And Origins

Fact origins are only `parser` and `derived`. Agent is not a fact origin.

Parser edges preserve relationship occurrence IDs and exact Evidence. Derived edges name a versioned rule and bounded contributing fact IDs. Aggregate edges include `occurrence_count`, `unique_source_count`, `unique_target_count`, confidence bounds, total contributor count, included contributor IDs, and contributor truncation.

### 4.4 Structures

- Cluster records contain bounded members, formation signals, internal/external unique-edge and occurrence counts, and SCC IDs.
- Layer records contain closed rule IDs, matched signals, confidence, members, or `unclassified`.
- Flows contain deterministic root, ordered steps/edges, static/runtime labels, terminal reason, confidence/coverage, and truncation.
- Tour items reference existing deterministic IDs and contain persisted rank signals. Agent guidance is separate.

### 4.5 Frozen Semantic Slots And Scope Contracts

`scope_contracts` is deterministic and ordered by `(scope_kind, scope_id)`. Each strict record contains exactly `scope_id`, `scope_kind`, `contract_hash`, `allowed_fact_node_ids`, `required_anchor_fact_node_ids`, `allowed_record_kinds`, and `allowed_claim_kinds`. `contract_hash` hashes the other six fields canonically. Scope IDs are existing cluster IDs, flow IDs, or tour-item IDs; tour-item records use `scope_kind: "tour"`.

Allowed fact-node expansion is closed:

| Scope | Allowed fact nodes | Required anchor fact nodes |
|---|---|---|
| cluster | repository node; member module/file nodes; symbols owned by member files | every direct member file, in persisted member order |
| flow | repository node; fact nodes referenced by root/steps/edges; owning file/module ancestors | root then every persisted step node, in flow order |
| tour | repository node; fact-node stop plus ancestors, or the complete allowed set of a referenced cluster/flow stop | the stop itself, or the referenced cluster/flow required anchors |

Ancestor order is symbol, file, module, repository; duplicates retain first occurrence. All ID arrays are then persisted in first-occurrence structural order, not set/hash iteration order.

Permissions are the intersection of these closed tables:

| Scope kind | Allowed record kinds |
|---|---|
| cluster | `cluster_label`, `concept` |
| flow | `flow_explanation`, `concept` |
| tour | `reading_guidance`, `concept` |

| Record kind | Allowed claim kinds |
|---|---|
| `cluster_label` | `label`, `summary`, `responsibility`, `association` |
| `flow_explanation` | `label`, `summary`, `flow_explanation`, `association` |
| `concept` | `label`, `summary`, `concept_description`, `association` |
| `reading_guidance` | `label`, `summary`, `reading_guidance`, `association` |

## 5. Derivation Contract

### 5.1 Snapshot And Classification Boundary

The map adapter reads one immutable validated `PublishedIndex` in stable path/ID order. It follows the active repository-classification spec where applicable:

- snapshot identity is repository fingerprint plus index build ID;
- path, language count/ratio, and named JSON/TOML manifest signals are bounded and registered;
- malformed/oversized manifests produce safe observation IDs, not guessed values;
- no ignored files, arbitrary prose classification, model output, raw SQL outside indexing, or source text in audit metadata.

Coverage records facts by language/parser/kind, skipped files, unresolved references, included/omitted counts, and truncation reasons.

### 5.2 Resolution And Lifting

MVP cross-file resolution is limited to Python qualified import/reference facts. Rules run from exact qualified/module matches to unique constrained short-name matches; ambiguous or unsupported references remain unresolved with bounded candidate metadata.

File nodes follow manifest paths. Python modules follow path/package boundaries, JS/TS modules use indexed package roots then parent directories, and other languages use a deterministic parent fallback. Symbols project through resolved targets to file/module edges.

### 5.3 Importance, Topology, Flows, Tour

Importance persists raw unique-neighbor signals and explicit rule matches. Display rank is a documented lexicographic tuple, not a hidden scalar.

Clusters start at package/directory boundaries. Deterministic undersized merging uses maximum cross-edge connectivity and stable IDs. Tarjan SCC reports cycles without rewriting direction. Closed layer path rules classify Interface/CLI, Application, Domain, Infrastructure, Persistence, Tests, or `unclassified`.

Schema 1.0 flow roots are Python top-level `main`/`entrypoint`, `__main__`, and resolved indexed `pyproject.toml` scripts. Allowed transitions are `calls` and labeled structural-fallback `imports`. Traversal never revisits a node in one path, deduplicates occurrence adjacency, suppresses only explicitly defined non-bridge utility nodes, and persists bounds/terminal reasons.

Tour order is deterministic: entrypoints, clusters, flows, then uncovered bridge modules, each with explicit stable rank tuples and `next_in_tour` adjacency.

## 6. Budget Contract

`map build` requires:

```text
--source-fact-budget N
--artifact-byte-budget BYTES
--budget-file PATH
```

The strict budget file is:

```json
{
  "schema_version": "1.0",
  "node_budget": 10000,
  "edge_budget": 30000,
  "contributing_relationship_ids_per_edge": 32,
  "resolution_candidates_per_reference": 8,
  "cluster_budget": 1000,
  "minimum_cluster_files": 2,
  "flow_budget": 100,
  "flow_depth": 5,
  "nodes_per_flow": 30,
  "edges_per_flow": 29,
  "tour_budget": 100,
  "evidence_snapshots": 200,
  "evidence_references_per_snapshot": 128,
  "enrichment_records": 1000,
  "records_per_scope": 32,
  "claims_per_record": 32,
  "fact_node_ids_per_claim": 32,
  "related_node_ids_per_claim": 32,
  "evidence_ids_per_claim": 16,
  "enrichment_input_bytes": 1000000
}
```

Every field is required, positive, range-checked, strictly decoded, and persisted as an effective value. No omitted field receives an unbounded or “reasonable” default. `source_fact_budget` fails rather than deriving a biased partial topology when required source inventory exceeds it. Output subbudgets may deterministically truncate only where the artifact records exact included/omitted counts and reasons. Essential endpoint closure cannot be truncated into dangling facts.

`artifact_byte_budget` is a capacity limit, not a derivation parameter. `map evidence` requires `--token-budget`; `map show` requires `--max-results`.

Field classification is normative:

| Class | Fields | Revision effect | Existing semantics |
|---|---|---|---|
| Derivation | budget `schema_version`, `source_fact_budget`, `node_budget`, `edge_budget`, `contributing_relationship_ids_per_edge`, `resolution_candidates_per_reference`, `cluster_budget`, `minimum_cluster_files`, `flow_budget`, `flow_depth`, `nodes_per_flow`, `edges_per_flow`, `tour_budget` | Changes `deterministic_revision` | Clear all snapshots/enrichments after successful rebuild |
| Semantic capacity | `evidence_snapshots`, `evidence_references_per_snapshot`, `enrichment_records`, `records_per_scope`, `claims_per_record`, `fact_node_ids_per_claim`, `related_node_ids_per_claim`, `evidence_ids_per_claim`, `enrichment_input_bytes` | Deterministic revision unchanged; artifact revision changes when persisted | Preserve only when current semantic state satisfies every new limit; otherwise `knowledge_map_capacity_conflict`, no write |
| Artifact capacity | top-level `artifact_byte_budget` | Deterministic/semantic revisions unchanged; artifact revision changes when persisted | Preserve only when complete current/candidate bytes fit; otherwise artifact-budget error, no write |
| Operational | output format and fixed bounded lock wait | No artifact/revision effect | Preserve |

All effective derivation and capacity values are persisted. No capacity reduction silently truncates or discards semantic state.

The Evidence command's required `--token-budget` is an operation-local selection bound persisted in snapshot identity/content, not a build-budget field; changing it may produce a different snapshot but never changes deterministic revision. Show's required `--max-results` is a read-only projection bound with no artifact effect.

## 7. Lifecycle And Semantic Reuse

### 7.1 Observed Artifact States

| State | Meaning | Valid recovery |
|---|---|---|
| `absent` | No artifact | `map build` |
| `current` | Strictly valid and matches current index | Any map command |
| `stale` | Valid artifact, changed repository/index identity | Re-index if needed, then `map build` |
| `invalid` | Unsupported/malformed/internally inconsistent artifact | Preserve for diagnosis; `map build` may replace under lock/CAS |

`locked` and `failed` are command outcomes, not persisted states.

### 7.2 Per-Scope Semantic State

| State | Definition |
|---|---|
| `pending` | No Evidence snapshot and no enrichment |
| `evidence_ready` | One current snapshot and no claims |
| `enriched` | One current snapshot and one or more accepted claim records |

Semantic completion is optional. `show` merges available labels/claims but deterministic fields remain authoritative. `validate` accepts all three current scope states.

### 7.3 Build Matrix

| Change | Deterministic revision | Evidence/enrichment | Write |
|---|---|---|---|
| Same index, schema, algorithm, derivation parameters, content, and capacity | unchanged | preserve | no-op |
| Semantic-capacity change and current semantic state satisfies all new limits | unchanged | preserve | update capacity and artifact revision |
| Semantic-capacity reduction below current usage | unchanged | preserve old bytes | fail `knowledge_map_capacity_conflict` |
| Artifact byte-budget change and current bytes fit | unchanged | preserve | update capacity and artifact revision |
| Index identity change | changed | clear all | publish rebuilt map |
| Derivation budget/rule/schema/algorithm change | changed | clear all | publish rebuilt map |
| Output format/lock wait | unchanged | preserve | no artifact effect |

No attempt is made in Version 1 to retain semantics across a deterministic-revision change; conservative invalidation is explicit and testable.

### 7.4 Evidence And Enrichment Replacement

Each scope owns at most one snapshot. Equivalent recollection is a no-op. Changed Evidence cannot overwrite cited Evidence; the caller runs `map reset --scope`, then recollects.

An enrichment input is a complete replacement for one scope and includes `expected_artifact_revision`. Identical content is a no-op. Different valid content may replace that scope only when the expected revision matches under the writer lock. This supplies a correction path without allowing partial merges.

Inside the lock, after current scope/Evidence/reference revalidation, compare the submitted canonical scope hash with the current scope hash first. An identical replay returns unchanged even when an unrelated scope advanced `artifact_revision`. Only a different valid scope hash enforces `expected_artifact_revision == current artifact_revision`; mismatch returns revision conflict.

`map reset --scope` removes that scope's Evidence and enrichment atomically, increments artifact revision, recomputes semantic revision, and leaves deterministic revision/sections byte-identical.

## 8. Agent Claim Contract

An enrichment submission contains one scope and bounded records. Long-form semantics are arrays of independently cited claims:

```json
{
  "schema_version": "1.0",
  "scope_id": "cluster:...",
  "expected_artifact_revision": 7,
  "records": [
    {
      "id": "concept:evidence-pipeline",
      "kind": "concept",
      "claims": [
        {
          "kind": "label",
          "text": "Evidence Pipeline",
          "fact_node_ids": ["module:..."],
          "related_node_ids": [],
          "evidence_ids": ["evidence:..."]
        },
        {
          "kind": "responsibility",
          "text": "The service validates persisted Evidence before publication.",
          "fact_node_ids": ["symbol:..."],
          "related_node_ids": ["module:..."],
          "evidence_ids": ["evidence:..."]
        }
      ]
    }
  ]
}
```

Claim kinds are closed: `label`, `summary`, `responsibility`, `flow_explanation`, `concept_description`, `reading_guidance`, and `association`. Each non-empty claim owns non-empty current Evidence IDs and fact-node IDs allowed by the scope contract. Optional related node IDs live only on the cited claim. Records contain only ID, kind, and claims; Agent-authored titles/labels/associations cannot exist outside claims. Record-level citations do not exist.

The complete persisted Evidence projection is one object per scope with exactly: `schema_version`, `scope_id`, `scope_kind`, `scope_contract_hash`, `deterministic_revision`, `repository_fingerprint`, `index_build_id`, `index_schema_version`, `source_control`, nullable `source_commit`, nullable `source_dirty`, `query`, `query_plan_hash`, `retrieval_parameters`, `token_budget`, `estimated_tokens`, `reserved_tokens`, `token_estimator`, `truncated`, `reference_count`, `references`, and `snapshot_hash`. `retrieval_parameters` contains exactly `max_results`, `strategy`, `rrf_k`, ordered `channel_weights`, and `overlap_threshold`. `references` contain exactly `evidence_id`, `chunk_id`, `content_hash`, `path`, `start_line`, `end_line`, nullable `symbol_id`, `role`, and ordered `anchor_fact_node_ids`. No collection timestamp or source text is persisted.

The complete persisted enrichment projection is one object per scope with exactly: `schema_version`, `scope_id`, `scope_kind`, `scope_contract_hash`, `evidence_snapshot_hash`, `canonical_input_bytes`, `canonical_input_sha256`, `records`, and `scope_content_hash`. Canonical input serializes only `schema_version`, `scope_id`, and normalized `records`; it excludes `expected_artifact_revision`. `scope_content_hash` hashes scope ID/kind, contract hash, snapshot hash, and normalized records. A fixed implementation reader ceiling is checked before decoding as invocation safety; after loading the artifact, both raw inbound bytes and canonical bytes must be at most persisted `enrichment_input_bytes`. Capacity compliance checks every persisted `canonical_input_bytes`, making build-time capacity reduction reproducible.

Validation proves syntactic validity, current ownership, referential integrity, and Evidence freshness. It does not prove logical entailment or semantic truth. Agent associations remain semantic and are never materialized as fact edges.

Evaluation keeps these dimensions separate:

- citation validity;
- referential integrity;
- Evidence freshness;
- deterministic reproducibility;
- semantic usefulness by explicit/manual fixture judgment.

## 9. Lock, Revision, And Atomic Publication

The deterministic child owns one `MapWriteTransaction` used by every writer. The lock path is transient `.repo-dive/knowledge-map.lock` and is not a public artifact.

The stdlib implementation uses an OS advisory exclusive file lock (`fcntl` on POSIX, `msvcrt` on Windows) with a fixed bounded wait recorded in executable help/error details. OS lock release on process exit avoids permanent stale-lock ownership. No daemon or remote lock service is added.

Writer protocol:

1. Strictly read baseline bytes when present and record `(artifact_revision, content_hash)` or an absent/invalid byte-hash sentinel.
2. Perform expensive derivation/retrieval/input decoding outside the lock.
3. Acquire the repository-local exclusive lock within the bounded wait.
4. Reload current complete bytes.
5. Revalidate the current published index identity and operation-specific scope/Evidence references.
6. Run a pure operation-specific equivalence check; if current state already exactly satisfies the submitted intent, return unchanged without a write.
7. For any remaining mutation, compare revision/content hash or sentinel with the expected baseline and fail on mismatch.
8. Construct and strictly validate the complete candidate.
9. Canonically serialize once and enforce count plus `artifact_byte_budget` limits.
10. Atomically replace `.repo-dive/knowledge-map.json` and release the lock in all paths.

A pre-lock hash check alone is forbidden because it leaves a TOCTOU window. The equivalence hook may only recognize the exact desired state already present; it cannot merge, rewrite, or ignore stale index/Evidence. A non-equivalent baseline mismatch returns `knowledge_map_revision_conflict`. `show` and `validate` are read-only and observe either the old or new complete file through atomic replacement.

## 10. CLI Commands

| Command | Mutates | Required bounds | Purpose |
|---|---:|---|---|
| `repo-dive map build <repository> --source-fact-budget N --artifact-byte-budget B --budget-file PATH --format json` | Yes | all shown | Build/rebuild deterministic map; enrichment optional |
| `repo-dive map show <repository> --view architecture\|flows\|tour --max-results N --format json` | No | `max-results` | Bounded projection plus identity/coverage/semantic counts |
| `repo-dive map evidence <repository> --scope ID --token-budget N --format json` | Yes | `token-budget` | Persist and return one scope Evidence snapshot |
| `repo-dive map enrich <repository> --input PATH\|- --format json` | Yes | persisted input/claim limits | Replace one scope's claim set under expected revision |
| `repo-dive map reset <repository> --scope ID --format json` | Yes | bounded one scope | Remove one scope's Evidence/enrichment for correction |
| `repo-dive map validate <repository> --format json` | No | artifact persisted bounds | Strict schema, reference, revision, ordering, and freshness check |

There is no `map status` in Version 1.

## 11. Error And Recovery Matrix

All failure rows write nothing and preserve the prior artifact unless stated as success.

| Command | Condition | Stable code | Exit | `retry_mode` | `recovery_action` |
|---|---|---|---:|---|---|
| all | Missing/invalid CLI flag or unsupported format; for build, malformed budget document | `invalid_invocation` | 2 | `after_recovery` | `correct_invocation` |
| all | Repository root does not exist | `repository_not_found` | 3 | `after_recovery` | `select_repository` |
| all | Repository root is temporarily unavailable | `repository_unavailable` | 3 | `after_cause_clears` | `wait_for_repository` |
| all | Repository root is not a directory | `repository_not_directory` | 3 | `after_recovery` | `select_repository` |
| build/enrich | Budget/input path escapes repository | `path_outside_repository` | 3 | `after_recovery` | `select_repository_input` |
| build/enrich | Budget/input path does not exist | `repository_path_not_found` | 3 | `after_recovery` | `select_existing_input` |
| build/enrich | Budget/input path is temporarily unavailable | `repository_path_unavailable` | 3 | `after_cause_clears` | `wait_for_input` |
| all | Published index missing | `index_not_found` | 3 | `after_recovery` | `index_repository` |
| all | Published index stale | `index_stale` | 3 | `after_recovery` | `rebuild_index` |
| writers | Lock wait expires | `knowledge_map_locked` | 3 | `unchanged` | `wait_for_writer` |
| writers | Baseline revision/hash changed | `knowledge_map_revision_conflict` | 3 | `after_reload` | `reload_artifact` |
| writers | Index replaced during operation | `knowledge_map_index_changed` | 3 | `unchanged` | `rerun_current_index` |
| writers | Canonical serialization/atomic replacement fails | `knowledge_map_write_failed` | 4 | `after_cause_clears` | `inspect_write_environment` |
| build | Required source facts exceed source budget | `knowledge_map_source_budget_exceeded` | 3 | `after_recovery` | `raise_source_budget_or_reduce_scope` |
| build | Required deterministic closure exceeds a subbudget | `knowledge_map_budget_exceeded` | 3 | `after_recovery` | `raise_named_budget` |
| build | Candidate exceeds artifact byte budget | `knowledge_map_artifact_budget_exceeded` | 3 | `after_recovery` | `raise_artifact_budget_or_lower_sublimits` |
| build | Reduced semantic capacity is below current usage | `knowledge_map_capacity_conflict` | 3 | `after_recovery` | `reset_or_restore_capacity` |
| build | Unexpected derivation failure | `knowledge_map_derivation_failed` | 4 | `after_cause_clears` | `inspect_safe_diagnostic` |
| evidence | Map absent | `knowledge_map_not_found` | 3 | `after_recovery` | `build_map` |
| evidence | Map stale | `knowledge_map_stale` | 3 | `after_recovery` | `rebuild_map` |
| evidence | Map invalid | `knowledge_map_invalid` | 3 | `after_recovery` | `preserve_and_rebuild_map` |
| evidence | Unknown scope ID | `knowledge_map_scope_not_found` | 3 | `after_recovery` | `select_current_scope` |
| evidence | Required complete Evidence exceeds token budget | `knowledge_map_evidence_budget_insufficient` | 3 | `after_recovery` | `raise_token_budget` |
| evidence | Snapshot count or required Evidence references exceed persisted capacity | `knowledge_map_evidence_capacity_exceeded` | 3 | `after_recovery` | `reset_scope_or_raise_capacity` |
| evidence | Different cited snapshot already exists | `knowledge_map_evidence_conflict` | 3 | `after_recovery` | `reset_scope_and_recollect` |
| evidence | Equivalent snapshot exists | success `unchanged: true` | 0 | N/A | N/A |
| enrich | Reader ceiling, UTF-8, JSON/duplicate-key, unknown/missing field, invalid kind/shape, or missing claim citation failure | `knowledge_map_enrichment_invalid` | 2 | `after_recovery` | `correct_submission` |
| enrich | Map absent | `knowledge_map_not_found` | 3 | `after_recovery` | `build_map` |
| enrich | Map stale | `knowledge_map_stale` | 3 | `after_recovery` | `rebuild_map` |
| enrich | Map invalid | `knowledge_map_invalid` | 3 | `after_recovery` | `preserve_and_rebuild_map` |
| enrich | Scope has no current snapshot | `knowledge_map_evidence_not_found` | 3 | `after_recovery` | `collect_evidence` |
| enrich | Snapshot/index is stale | `knowledge_map_evidence_stale` | 3 | `after_recovery` | `rebuild_reset_recollect` |
| enrich | Unknown/wrong-scope node or Evidence ID | `knowledge_map_enrichment_reference_invalid` | 3 | `after_recovery` | `regenerate_current_scope_submission` |
| enrich | Persisted count/byte capacity exceeded | `knowledge_map_enrichment_budget_exceeded` | 3 | `after_recovery` | `reduce_enrichment_or_raise_capacity` |
| enrich | Equivalent scope payload | success `unchanged: true` | 0 | N/A | N/A |
| reset | Map absent | `knowledge_map_not_found` | 3 | `after_recovery` | `build_map` |
| reset | Map stale | `knowledge_map_stale` | 3 | `after_recovery` | `rebuild_map` |
| reset | Map invalid | `knowledge_map_invalid` | 3 | `after_recovery` | `preserve_and_rebuild_map` |
| reset | Unknown scope | `knowledge_map_scope_not_found` | 3 | `after_recovery` | `select_current_scope` |
| reset | Scope already pending | success `unchanged: true` | 0 | N/A | N/A |
| validate | Map absent | `knowledge_map_not_found` | 3 | `after_recovery` | `build_map` |
| validate | Map stale | `knowledge_map_stale` | 3 | `after_recovery` | `rebuild_map` |
| validate | Unsupported/malformed artifact | `knowledge_map_invalid` | 3 | `after_recovery` | `preserve_and_rebuild_map` |
| validate | Persisted Evidence snapshot/index is stale | `knowledge_map_evidence_stale` | 3 | `after_recovery` | `rebuild_reset_recollect` |
| show | Unknown view or missing/invalid `max-results` | `invalid_invocation` | 2 | `after_recovery` | `correct_invocation` |
| show | Map absent | `knowledge_map_not_found` | 3 | `after_recovery` | `build_map` |
| show | Map stale | `knowledge_map_stale` | 3 | `after_recovery` | `rebuild_map` |
| show | Map invalid | `knowledge_map_invalid` | 3 | `after_recovery` | `preserve_and_rebuild_map` |
| read commands | Unexpected internal read/projection failure | `internal_operation_failed` | 4 | `after_cause_clears` | `inspect_safe_diagnostic` |

Map errors use the existing Schema 1.0 `ErrorEnvelope`. For every non-success map error, `error.details` contains required string fields `retry_mode` and `recovery_action` with exactly the values in the matrix. `retry_mode` is closed to `unchanged`, `after_reload`, `after_recovery`, and `after_cause_clears`; success rows have neither field. `recovery_action` is closed to the values present in the matrix. Additional details are bounded condition-specific scalars/IDs/counts only; `error.message` is safe human text and is not a machine contract.

Failure precedence is normative and stops at the first applicable condition:

1. CLI flag/format validation and build budget-document byte/UTF-8/JSON/schema validation, producing `invalid_invocation`.
2. Existing repository-root and command input-path confinement/read errors, retaining their existing repository codes.
3. Enrich payload reader-ceiling/UTF-8/JSON/duplicate-key/schema validation, producing only `knowledge_map_enrichment_invalid`.
4. Published-index missing/stale/identity errors.
5. Map absent, then strict map decode/invalid, then map/index freshness.
6. Scope existence, snapshot existence/freshness/conflict, claim/reference validity, then operation token/count/input capacities.
7. Writer lock timeout.
8. Under-lock index replacement and repeated map/scope/Evidence/reference validation.
9. Exact current-intent equivalence success; otherwise baseline revision/hash conflict, followed by repeated capacity validation.
10. Complete candidate validation, artifact-byte capacity, canonical serialization, then atomic replacement.
11. The command-specific internal code when defined; otherwise `internal_operation_failed`.

Thus combined phrases such as “map absent/stale/invalid” are shorthand only in prose: the emitted code is one exact row selected by this order. A post-lock index change wins over a simultaneous revision conflict because freshness is required before equivalence or CAS.

Shared rows above expand into independent command/error contracts as follows; every checked cell requires its own process-level test, including code, exit, no-write bytes, retry classification, and recovery fields:

| Stable code | build | evidence | enrich | reset | validate | show |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `invalid_invocation` | yes | yes | yes | yes | yes | yes |
| `repository_not_found` | yes | yes | yes | yes | yes | yes |
| `repository_unavailable` | yes | yes | yes | yes | yes | yes |
| `repository_not_directory` | yes | yes | yes | yes | yes | yes |
| `path_outside_repository` | yes | no | yes | no | no | no |
| `repository_path_not_found` | yes | no | yes | no | no | no |
| `repository_path_unavailable` | yes | no | yes | no | no | no |
| `index_not_found` | yes | yes | yes | yes | yes | yes |
| `index_stale` | yes | yes | yes | yes | yes | yes |
| `knowledge_map_locked` | yes | yes | yes | yes | no | no |
| `knowledge_map_revision_conflict` | yes | yes | yes | yes | no | no |
| `knowledge_map_index_changed` | yes | yes | yes | yes | no | no |
| `knowledge_map_write_failed` | yes | yes | yes | yes | no | no |
| `knowledge_map_not_found` | no | yes | yes | yes | yes | yes |
| `knowledge_map_stale` | no | yes | yes | yes | yes | yes |
| `knowledge_map_invalid` | no | yes | yes | yes | yes | yes |
| `internal_operation_failed` | yes | yes | yes | yes | yes | yes |

Command-specific rows remain required in addition to this expansion. The generic `invalid_invocation` row explicitly excludes enrichment payload bytes/encoding/JSON/schema, which always use `knowledge_map_enrichment_invalid`. `map validate` and `map show` accept syntactically valid invocations without extra payload flags, but malformed optional format/value input still uses `invalid_invocation`.

## 12. Wiki And Tooling Boundaries

Version 1 does not generate `wiki_topics`, call or alter `wiki init`, change Wiki Schema 2.0, modify templates, or add a Wiki dependency on Knowledge Map. The active Wiki template spec is a negative boundary: classification plus the built-in registry remains the sole owner of governed Wiki structure.

No Agent plugin/skill or generated Host tooling is added. If implementation later adds repository-owned files referenced by instructions, the active tooling-integration spec requires the full referenced closure and exact clean-snapshot validation. Staging remains allowlisted and unrelated dirty files stay excluded.

## 13. Rollout And Rollback

1. Ship relationship occurrence Schema as an independently verified prerequisite.
2. Ship deterministic package/store/build/views without public CLI registration.
3. Ship Evidence/enrichment against the frozen shared transaction API.
4. Expose CLI and complete evaluation/docs only after domain contracts pass.

Relationship rollback reverts parser and SQLite compatibility versions together. Deterministic-map rollback removes/disables the additive command/package but never deletes repository-owned artifacts automatically. Evidence/enrichment can be disabled while deterministic artifacts with empty semantic arrays remain valid. Existing Wiki artifacts remain untouched in all cases.

## 14. Risks

| Risk | Mitigation |
|---|---|
| Occurrences multiply traversal/ranking | Separate occurrence storage from unique adjacency and regression-test structural scores/order |
| Sparse non-Python facts mislead views | Persist language coverage and unresolved counts; never let Agent fill fact gaps |
| Conservative invalidation discards useful semantics | Explicit deterministic-revision rule; correctness over speculative reuse in V1 |
| JSON read-modify-write loses updates | One bounded OS writer lock plus post-lock revision/hash comparison |
| Artifact grows through repeated semantic calls | One snapshot per scope, complete-scope replacement, strict count/citation/input/artifact limits |
| Citation presence is mistaken for truth | Claim-level citations and separate referential/freshness/usefulness metrics; no entailment claim |
| Public API grows prematurely | No status/Wiki topics/graph alias; closed schemas and one naming system |
