# Map Evidence And Enrichment Design

## Ownership

```text
knowledge_map/evidence.py             pure scope plan and bounded selection
knowledge_map/evidence_service.py     retrieval plus snapshot mutation
knowledge_map/submission.py           strict claim document decoder/validator
knowledge_map/enrichment_service.py   complete-scope replacement and reset
```

These modules import deterministic models and `MapWriteTransaction`. They do not write JSON directly, introduce locks, change deterministic sections, or depend on Wiki.

## Scope Contract

Evidence is available for cluster, flow, and tour scopes. The persisted deterministic scope contract contains:

- scope ID/kind and contract hash;
- allowed fact-node IDs;
- closed record/claim kinds;
- required anchor fact-node IDs.

The Evidence response augments that immutable contract with the current deterministic revision, allowed Evidence IDs after collection, and all persisted count/byte limits.

It consumes, without widening, the exact parent/Child 2 scope expansion and permission tables. Cluster contracts allow repository, member module/file, and member-owned symbol facts; flow contracts allow repository, root/step/edge facts and owning ancestors; tour contracts allow repository plus the stop/ancestor set or referenced cluster/flow contract. Record and claim permissions are the exact parent table intersection. Any ID or kind outside the persisted contract is wrong-scope input.

The contract is data, not a prompt. The caller may use any Agent/model or no model; the CLI never invokes one.

## Evidence Planning

Required anchors and representative selection:

- cluster: one representative complete chunk for every direct member file, in persisted member order;
- flow: one representative complete chunk for the root and each persisted step node, in flow order;
- tour item: one representative for a fact-node stop, or the referenced cluster/flow mandatory sequence.

For a symbol anchor, use its exact definition chunk; a reference without one falls back to its owning file. For a file/module anchor, choose the first definition chunk by `(path, start_line, end_line, symbol_kind_order, qualified_name, symbol_id, chunk_id)`, where kind order is `module`, `class`, `function`, `method`, `reference`; when no definition exists, choose the first complete file chunk by `(path, start_line, end_line, chunk_id)`. A module considers contained files in POSIX path order. Deduplicate by chunk ID while retaining first anchor occurrence and append all anchor fact-node IDs mapped to that chunk. These rules, the scope contract hash, ordered anchor IDs, and retrieval parameters form `query_plan_hash`.

Required complete chunks reserve tokens before supplemental retrieval. Supplemental retrieval uses the existing bounded search/fusion pipeline with a deterministic query derived from scope facts. It cannot displace direct Evidence.

If all mandatory complete chunks do not fit the operation token budget, return `knowledge_map_evidence_budget_insufficient` as repository/requested-data exit `3`, include numeric required/provided token estimates, and persist nothing. If snapshot count or mandatory reference count exceeds persisted `evidence_snapshots` or `evidence_references_per_snapshot`, return `knowledge_map_evidence_capacity_exceeded` exit `3` with required/provided counts and persist nothing. Supplemental references truncate deterministically at both token and reference limits with included/omitted counts.

## Snapshot Identity

One snapshot per scope uses exactly the parent projection, including source-control identity, deterministic query text/hash, exact retrieval parameters, token accounting/estimator/truncation, ordered refs, and snapshot hash. Each reference uses exactly the parent chunk/hash/POSIX range/nullable symbol/role/anchor projection. Source text is returned to the caller but does not become a fact node.

Equivalent snapshot content is a no-op. A changed snapshot can replace an uncited snapshot. If accepted enrichment cites the current snapshot, replacement returns `knowledge_map_evidence_conflict`; reset is required first.

## Submission Schema

```json
{
  "schema_version": "1.0",
  "scope_id": "flow:...",
  "expected_artifact_revision": 12,
  "records": [
    {
      "id": "flow-explanation:...",
      "kind": "flow_explanation",
      "claims": [
        {
          "kind": "label",
          "text": "Index publication",
          "fact_node_ids": ["symbol:..."],
          "related_node_ids": [],
          "evidence_ids": ["evidence:..."]
        },
        {
          "kind": "flow_explanation",
          "text": "The service validates the staged generation before replacing the current pointer.",
          "fact_node_ids": ["symbol:..."],
          "related_node_ids": ["module:..."],
          "evidence_ids": ["evidence:..."]
        }
      ]
    }
  ]
}
```

Record kinds are `cluster_label`, `flow_explanation`, `concept`, and `reading_guidance`. Claim kinds are `label`, `summary`, `responsibility`, `flow_explanation`, `concept_description`, `reading_guidance`, and `association`. Every claim owns citations and contains its own bounded `related_node_ids` array. Records have no Agent-authored title or related-node field outside claims. Unknown fields and empty/padded/duplicate IDs fail strict decoding.

Claim-level `related_node_ids` is an evidence-cited association only. It never creates a deterministic edge.

## Validation Order

1. Read exactly one JSON document under the fixed implementation reader ceiling and decode UTF-8/JSON strictly.
2. Validate exact fields/schema/enums/scalar/collection limits.
3. Load a current map snapshot and exact persisted scope contract; enforce the persisted `enrichment_input_bytes` against raw inbound bytes.
4. Validate current deterministic revision and Evidence snapshot hash/index identity.
5. Validate every record/claim/reference and scope ownership.
6. Canonically serialize `schema_version`, `scope_id`, and normalized `records` only; enforce canonical input bytes and calculate its bytes/hash plus scope content hash.
7. Enter `MapWriteTransaction`, reload, and repeat state/reference/capacity checks.
8. Compare current and submitted scope content hashes first; if equal, return unchanged regardless of an unrelated artifact-revision advance.
9. For different content only, enforce `expected_artifact_revision`, replace the complete scope, and persist the exact parent enrichment projection.
10. Validate/serialize/final-byte-check the full artifact and atomically replace.

Reader-ceiling, invalid UTF-8/JSON, duplicate-key, malformed shape, missing claim citation, and unsupported schema/kind failures all use `knowledge_map_enrichment_invalid` exit `2`; none use generic `invalid_invocation`. Repository/input-path errors retain existing repository codes. Unknown map/scope/node/Evidence IDs, wrong scope, stale Evidence, revision conflict, and capacity exceeded by repository state are exit `3`. Unexpected internal/write failures are exit `4`.

## Complete-Scope Replacement

Submissions are not partial merges. The ordered `records` array is the full desired semantic state for one scope. The persisted scope object contains the parent-exact contract/snapshot bindings, `canonical_input_bytes`, `canonical_input_sha256`, records, and scope content hash. Same scope content hash is unchanged under the lock before expected-revision enforcement. Different valid content replaces only that scope when `expected_artifact_revision` still matches. Artifact and semantic revisions change; deterministic revision and deterministic sections remain byte-identical.

## Reset

The reset domain operation validates a current scope, enters the shared transaction, removes its snapshot and records, recomputes semantic/content hashes, increments artifact revision, and preserves deterministic bytes/revision. Reset of an already pending scope is unchanged. This is the only V1 route for replacing cited Evidence.

## Concurrency

Evidence retrieval and input parsing may occur outside the lock. No result is published until the shared transaction reloads and validates index/scope state. If current state already exactly satisfies the operation, the pure equivalence hook returns unchanged; all non-equivalent concurrent build or semantic writes conflict, with no automatic merge. Tests coordinate multiple processes/transactions, not only mocked hash checks.

## Semantic Validation Limit

The validator asserts citation validity, scope ownership, referential integrity, and freshness. It explicitly does not assert logical entailment. Evaluation keeps semantic usefulness as a separate fixture/manual judgment.

## Rollback

Disable/remove semantic services while retaining deterministic artifacts with empty semantic arrays. Never delete existing repository-owned map files automatically. Any required change to shared models/store/build returns to deterministic-child planning rather than adding a semantic-owned workaround.
