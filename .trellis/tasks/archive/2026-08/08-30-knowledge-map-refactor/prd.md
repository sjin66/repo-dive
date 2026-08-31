# Knowledge Map Refactor

## Goal

Make Knowledge Map a queryable, verifiable, repository-owned structured model from which architecture, static-flow, and guided-reading views are derived. Parser facts establish what exists, deterministic algorithms establish structure and importance, and an optional calling Agent explains selected scopes through claim-level Evidence citations.

The deterministic Knowledge Map must be independently buildable, validatable, and useful without any Agent enrichment.

## Product Naming

- Public concept: **Knowledge Map**.
- CLI family: `repo-dive map`.
- Python package: `repo_dive.knowledge_map`.
- Public artifact: `.repo-dive/knowledge-map.json`.
- Internal source structure: **deterministic fact graph**.

Version 1 must not expose a parallel public `graph` command, `knowledge_graph` package, or `knowledge-graph.json` artifact.

## Confirmed Current State

- The published index already contains immutable `Chunk`, `Symbol`, and `Relationship` values and bounded symbol traversal.
- `Relationship` currently has no deterministic occurrence ID or edge-local path/range, and persistence collapses repeated endpoint/kind/provenance relationships.
- Python parsing emits `contains`, `imports`, `calls`, and `inherits`; JS/TS currently emits symbols and `contains` only.
- Cross-file canonical reference resolution, file/module lifting, importance, SCCs, clusters, layers, flows, reading tours, generic semantic claims, and Knowledge Map persistence do not exist.
- Atomic replace prevents partial files but does not prevent concurrent read-modify-write lost updates.
- Existing classification and Wiki contracts provide reusable strict deterministic snapshot and Evidence-validation patterns, but remain independent owners.

## Capability Map

| Capability | Owning child | Dependency |
|---|---|---|
| Exact per-occurrence relationship facts and index compatibility | `08-30-relationship-provenance-index-schema` | None |
| Deterministic map, shared writer protocol, lifting, analysis, flows, tour, build, and views | `08-30-deterministic-knowledge-map` | Relationship child complete |
| Scope Evidence and claim-level Agent enrichment | `08-30-map-evidence-enrichment` | Deterministic model/store/build contracts frozen |
| Public CLI, error integration, security/recovery/performance/evaluation, bilingual docs | `08-30-map-cli-docs-evaluation` | Deterministic and enrichment children complete |

The parent owns cross-child contracts and final integration review only. It is not an implementation target.

## Requirements

### KM-R1: Verifiable Relationship Occurrences

- Every parser syntax occurrence is one independent persisted `Relationship`, including repeated calls from the same source symbol to the same target.
- Each occurrence has a deterministic ID, provenance, repository-relative POSIX path, exact one-based inclusive start/end lines, and a stable occurrence discriminator sufficient to distinguish same-line duplicate endpoints.
- Graph traversal deduplicates reachability by `(source_id, target_id, kind)` so repeated occurrences do not repeat expansion.
- Aggregate edges persist `occurrence_count` and only a bounded ordered list of contributing relationship IDs.
- Importance fan-in/fan-out uses unique neighboring nodes; aggregate occurrence counts remain separately observable.
- Structural retrieval preserves its current ranking semantics unless a separately evaluated behavior change is approved.
- Parser/index Schema, parser version, manifest compatibility, and rebuild behavior change as one independently rollbackable prerequisite.

### KM-R2: Deterministic Fact Graph And Origins

- Public fact nodes are exactly `repository`, `module`, `file`, and `symbol` in Version 1.
- Chunks are represented through Evidence snapshots/references, not copied into public fact nodes.
- Fact nodes and edges have only `parser` or `derived` origin. Agent records live only under `enrichments` and never become fact nodes, edges, clusters, layers, flows, or tour order.
- Every parser or derived record traces to current parser relationship/symbol IDs and exact source Evidence where applicable.
- Map consumers read one validated published index generation through supported read-only interfaces and never mutate SQLite.

### KM-R3: Deterministic Structure And Analysis

- Lift symbols into file and language-aware module/package nodes using explicit versioned rules.
- Resolve only supported Python qualified references conservatively; ambiguity and unsupported language coverage remain explicit.
- Aggregate file/module edges with unique-neighbor and occurrence metrics, confidence bounds, derivation rules, and bounded contributing IDs.
- Persist explainable raw importance signals, including unique fan-in/fan-out, cross-module bridges, entrypoint/public API rules, documentation mentions, and distinct testing files.
- Form deterministic package/directory clusters, report SCC cycles, apply closed layer rules, and use `unclassified` for ambiguous or insufficient signals.
- Every new heuristic has an evaluation fixture demonstrating intended behavior without unsupported facts.

### KM-R4: Bounded Flows And Reading Tour

- Flow roots and traversable edge kinds are closed, versioned deterministic registries.
- Traversal is cycle-safe and bounded by persisted depth/node/edge/flow limits.
- Runtime and structural transitions remain distinguishable; static flows are never represented as guaranteed runtime traces.
- Utility suppression, path ordering, deduplication, truncation, and terminal reasons are explicit and deterministic.
- The reading tour has a deterministic rank/order and Agent content cannot reorder it.

### KM-R5: Independent Deterministic Lifecycle

The required workflow is:

```text
repo-dive index
  -> repo-dive map build
  -> repo-dive map show --view architecture|flows|tour

optional:
repo-dive map evidence --scope <scope-id>
  -> calling Agent generates enrichment
  -> repo-dive map enrich --input <file|->
  -> repo-dive map validate
```

- `map build` publishes a valid deterministic artifact with empty Evidence/enrichment sections.
- `map show` and `map validate` never require semantic completion.
- Missing enrichment changes presentation only; it never blocks deterministic views.
- Version 1 has no `map status`; bounded identity, coverage, truncation, and semantic counts are returned by `map show`, while `map validate` owns health checks.
- `map reset --scope <scope-id>` is the explicit revision-checked recovery path that removes only one scope's Evidence snapshot and enrichments so corrected Evidence can be collected. It never changes deterministic facts.

### KM-R6: Build Reuse And Invalidation

- Same current index, Knowledge Map schema/algorithm, derivation parameters, and deterministic content returns `unchanged: true`, performs no write, and preserves Evidence/enrichments and revision.
- Index identity or derivation-parameter change creates a new deterministic revision and conservatively clears all Evidence/enrichments.
- A changed semantic or artifact capacity preserves current semantics only when all persisted content fits the new limits; otherwise the build fails without mutation.
- Output format and bounded lock timeout are operational and never affect artifact identity.
- Source/index drift makes an existing artifact observably stale without rewriting it.

### KM-R7: Concurrency And Last-Valid Preservation

- `map build`, `map evidence`, `map enrich`, and `map reset` use one repository-local bounded writer-lock protocol.
- The artifact persists a positive monotonic `artifact_revision`, deterministic/semantic content hashes, and a top-level content hash.
- Writers perform expensive work outside the lock where possible, acquire the lock, reload current bytes, revalidate current index/references, detect whether current state already exactly satisfies the intent, and otherwise compare expected revision/content hash before validating and atomically replacing the complete candidate.
- A revision mismatch, lock timeout, or changed index returns a stable repository-state error and never silently merges or overwrites.
- A hash check without the lock is not considered sufficient compare-and-swap protection.
- Every failed operation preserves the previous valid artifact bytes.

### KM-R8: Budget Contract

- `map build` requires `--source-fact-budget`, `--artifact-byte-budget`, and a strict versioned `--budget-file` containing all traversal, aggregation, cluster, flow, tour, evidence-reference, and semantic-count sublimits. There are no implicit unbounded defaults.
- All effective budget values are persisted in the artifact.
- Every budget field is classified as derivation-affecting, semantic-capacity, artifact-capacity, or operational; its revision and semantic-preservation effect is explicit.
- Reducing a semantic-capacity field below current persisted usage returns a capacity conflict and writes nothing; it never silently drops claims or Evidence.
- Invalid/missing budget syntax is exit `2`; repository-required deterministic data that cannot fit is exit `3`.
- `map evidence` always requires `--token-budget`; required complete Evidence that cannot fit is exit `3` and persists nothing.
- `map show` always requires `--max-results` and returns explicit truncation metadata.

### KM-R9: Scope Evidence And Claim-Level Semantics

- Evidence snapshots are independently bounded, scope-owned, tied to the deterministic revision and current index, and contain stable Evidence references to complete chunks.
- Every Agent-authored label, summary, responsibility, flow explanation, concept description, reading guidance, or association is a separate claim with its own `text`, `fact_node_ids`, and `evidence_ids`.
- Cluster, flow, and tour scope contracts have closed fact-node expansion, record/claim permissions, mandatory-anchor selection, and stable tie-break rules persisted in the deterministic artifact.
- Summary claims, responsibilities, flow explanations, concept descriptions, and reading guidance cannot share only one record-level citation set.
- Strict decoding rejects unknown fields, unsupported kinds, duplicate IDs, dangling/wrong-scope references, stale Evidence, oversized input, and attempts to submit deterministic facts or lifecycle fields.
- Identical replay is idempotent. Changed scope content is accepted only as a complete replacement with the caller's expected artifact revision under the shared lock.
- Each persisted scope enrichment records canonical payload bytes/hash excluding `expected_artifact_revision`; this is the reproducible usage metric for `enrichment_input_bytes` capacity checks.
- Validation proves citation validity, ownership, referential integrity, and freshness; it does not prove that natural-language claims are logically entailed by Evidence.
- Agent associations remain semantic records and cannot project into parser/derived fact edges.

### KM-R10: Public Contract And Errors

- All commands are non-interactive, support `--format json`, emit one result/error document to stdout, send diagnostics to stderr, and emit no ANSI in JSON mode.
- Every command/error pair has a stable code, exit code, write/no-write behavior, retry classification, and recovery action in `design.md`.
- Error `details` use closed machine enums for retry/recovery, and overlapping failures follow one specified precedence order.
- Diagnostics never disclose source chunks, secrets, tokens, environment dumps, stack traces, or host-specific absolute repository paths.

### KM-R11: Compatibility, Evaluation, And Documentation

- Existing `index`, `search`, `context`, retrieval, and Wiki observable contracts remain compatible, including structural ranking.
- Version 1 does not generate `wiki_topics`, change `wiki init`, change Wiki Schema 2.0, or make Wiki consume Knowledge Map.
- The Knowledge Map implementation does not depend on Wiki; the Wiki template spec is only a negative ownership boundary.
- No graph database, implicit model call, Agent plugin/skill installation, interactive UI, or complex community-detection dependency is added.
- Evaluation reports citation validity, referential integrity, Evidence freshness, deterministic reproducibility, and semantic usefulness/manual fixture judgment as separate metrics. It must not call citation presence “100% grounding precision.”
- Implementation-time user/developer documentation is updated in matched English/Chinese pairs only after executable behavior exists.
- Final verification includes clean-snapshot repository-contract checks required by active tooling specs.

## Acceptance Criteria

- **KM-AC1 Relationship occurrences:** repeated same-endpoint syntax occurrences round-trip independently with stable exact provenance, while traversal and structural retrieval do not duplicate expansion or change existing rank behavior.
- **KM-AC2 Determinism:** a fixed index and fixed derivation budgets produce byte-stable deterministic sections, IDs, ordering, raw signals, clusters, SCCs, layers, flows, and tour.
- **KM-AC3 Traceability:** every public parser/derived edge and aggregate traces to current fact IDs; aggregate occurrence and unique-neighbor semantics are separately testable; no dangling IDs persist.
- **KM-AC4 Bounds:** source facts, nodes, edges, contributor IDs, candidates, clusters, flows, tour, snapshots, Evidence references per snapshot, claims, node references, citations, input bytes, and artifact bytes are explicitly bounded and expose stable truncation/failure details; capacity reduction below current usage fails without mutation.
- **KM-AC5 Independent use:** `map build -> map show` succeeds offline without Evidence or enrichment; `map validate` accepts a current deterministic-only artifact.
- **KM-AC6 Semantic claims:** every accepted natural-language claim has its own current scope-owned Evidence IDs and fact-node references; invalid or stale references fail without a write.
- **KM-AC7 Reuse/invalidation:** identical build is a no-op preserving semantics; index/derivation changes clear semantics; semantic/artifact capacity changes preserve only compliant content and reject reductions below current usage; scope reset removes only that scope's semantics.
- **KM-AC8 Concurrency:** contested writers, lock timeout, revision conflict, index replacement, validation failure, and atomic-write failure never lose a successful update or damage the previous artifact.
- **KM-AC9 CLI/errors:** every command and stable error row passes process-level JSON, exit, retry, recovery, bounded-output, and no-write assertions.
- **KM-AC10 Views:** architecture, flows, and tour reference only persisted map IDs, report partial static coverage, and never introduce Agent facts or Wiki topics.
- **KM-AC11 Compatibility/quality:** existing index/retrieval/context/Wiki suites remain green; every heuristic has an evaluation case; security, recovery, and performance tests pass.
- **KM-AC12 Release contract:** `make check` and `make test-all` pass from a freshly prepared clean snapshot, and matched English/Chinese implementation docs reflect executable help exactly.

## Out Of Scope

- Any public `repo-dive graph` command, `repo_dive.knowledge_graph` package, or `.repo-dive/knowledge-graph.json` artifact.
- Wiki topics, Wiki structure suggestions, `wiki init` changes, Wiki Schema changes, or automatic/flag-gated Wiki consumption.
- Source chunks as public graph nodes.
- JS/TS import/call/inheritance expansion or broad cross-language canonical resolution.
- Graph databases, query languages, network services, interactive visualization, Mermaid as authoritative storage, or complex community detection.
- Implicit generative/embedding calls, Agent-created facts, Agent plugin/skill installation, remote generation, or cross-repository maps.
- Semantic entailment proof; Version 1 validates references and freshness only.

## Open Questions

None. Any change to naming, Wiki ownership, semantic reset/replacement, or the command set requires a new planning review.
