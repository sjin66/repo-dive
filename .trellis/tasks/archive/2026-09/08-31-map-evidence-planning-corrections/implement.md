# Knowledge Map Evidence Planning Implementation Plan

## V1: Red Store And Scaling Tests

- Add Store tests for empty, bounded, oversized, duplicate/invalid, stable ordered, and
  multi-batch path lookups.
- Add an N-file one-scope test that records direct planning Store/query activity.
- Assert zero `get_parse_result` calls and zero direct Relationship reads.

## V2: Add Typed Chunk Lookup

- Implement the smallest read-only `IndexStore.get_chunks_by_paths` method with the
  existing Chunk row decoder and stable ordering.
- Keep batching policy in the Evidence adapter; add no database schema or index unless
  measured query plans show the existing `chunks.file_path` index is insufficient.

## V3: Scope-Directed Planning

- Resolve scope existence before direct fact loading.
- Freshness-validate any existing snapshot for that scope before replacement planning.
- Expand required Anchors to deterministic file paths from persisted nodes.
- Batch complete Chunk reads and referenced Symbol reads at 256 items.
- Pass those scoped facts through the unchanged pure planning and mandatory preflight
  sequence before supplemental retrieval.

## V4: Unavailable Evidence

- Add failing pure/integration/process cases for empty and skipped required Anchors.
- Add `knowledge_map_evidence_unavailable` and
  `make_source_indexable_or_select_scope` to the closed public mappings.
- Assert exit `3`, exact JSON envelope, safe bounded details, precedence, no
  supplemental search, and byte preservation.
- Pin precedence after map/source/scope and stale-existing-snapshot errors but before
  capacity, token, and supplemental-retrieval work.
- Update active spec plus matched EN/zh-CN CLI/workflow documentation.

## V5: Verify

Run indexing Store, Evidence planner/service, enrichment lifecycle, process matrix,
security, recovery, performance, repository-contract, retrieval compatibility, and
Wiki suites. Run `make check` and exact clean-snapshot gates before independent review.

## Rollback Gate

If scoped loading cannot preserve module/repository fallback or query-plan identity,
return to planning. Do not silently omit required Anchors or substitute unrelated
Chunks.
