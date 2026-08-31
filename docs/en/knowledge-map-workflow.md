# Knowledge Map Workflow

## Boundary

Knowledge Map is an optional repository-owned structured artifact. The CLI derives facts and views deterministically and never invokes a generative model. Agent claims are optional and remain separate from deterministic facts. This workflow does not change the Wiki workflow.

## Build And Inspect

Create the strict Schema `1.0` budget file inside the repository before indexing:

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

Every field is required and positive. `--source-fact-budget` and derivation fields affect deterministic identity; Evidence/enrichment fields are semantic capacities; `--artifact-byte-budget` bounds the complete serialized artifact.

Then run:

```text
repo-dive index <repository> --format json
repo-dive map build <repository> --source-fact-budget 10000 --artifact-byte-budget 5000000 --budget-file map-budgets.json --format json
repo-dive map show <repository> --view architecture --max-results 50 --format json
repo-dive map show <repository> --view flows --max-results 50 --format json
repo-dive map show <repository> --view tour --max-results 50 --format json
repo-dive map validate <repository> --format json
```

An identical build is a no-write success. A changed index or derivation budget creates a new deterministic revision and clears semantic state. Capacity changes preserve semantics only when all current values still fit.

## Optional Evidence And Enrichment

Choose a `scope_id` from the persisted scope contracts or bounded views, collect Evidence, let the calling Agent produce one strict claim submission, then validate:

```text
repo-dive map evidence <repository> --scope <scope-id> --token-budget 12000 --format json
repo-dive map enrich <repository> --input enrichment.json --format json
repo-dive map validate <repository> --format json
```

Each claim independently owns non-empty `fact_node_ids` and `evidence_ids`; `related_node_ids` may be empty. The submission's `expected_artifact_revision` protects corrections from overwriting concurrent work. Identical scope content is a no-write replay even if an unrelated scope advanced the artifact revision.

Empty or skipped files remain visible in deterministic cluster and tour scopes. If a required scope Anchor has no complete indexed Chunk, Evidence collection exits `3` with `knowledge_map_evidence_unavailable` and recovery action `make_source_indexable_or_select_scope`; it performs no supplemental retrieval and does not mutate the Map. Make the source indexable and rebuild the index and Map, or select another current scope.

Validation checks schema, current references, scope ownership, and Evidence freshness. It returns `semantic_entailment_checked: false`: citations are not proof that claim text is true or entailed.

## Reset And Recovery

When cited Evidence must change, reset only that scope and recollect it:

```text
repo-dive map reset <repository> --scope <scope-id> --format json
repo-dive map evidence <repository> --scope <scope-id> --token-budget 12000 --format json
```

For `index_not_found` or `index_stale`, index the repository. For `knowledge_map_not_found` or `knowledge_map_stale`, build the map. For `knowledge_map_locked`, wait for the current writer. For `knowledge_map_revision_conflict`, reload current state and regenerate the intended replacement. Every failed writer preserves the last valid `.repo-dive/knowledge-map.json` bytes.

## Wiki Independence

Knowledge Map has no Wiki projection in Version 1. Continue to use `wiki classify -> wiki init -> wiki evidence -> calling Agent generation -> wiki page -> wiki validate -> wiki build` for Wiki publication. Generic Map Evidence cannot substitute for persisted Wiki Evidence.
