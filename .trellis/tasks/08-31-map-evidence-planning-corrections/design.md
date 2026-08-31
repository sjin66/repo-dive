# Knowledge Map Evidence Planning Corrections Design

## Store Boundary

Add one typed read-only `IndexStore` method for complete Chunks by path batch. It uses
the existing Chunk projection, `WHERE file_path IN (...)`, and stable
`ORDER BY file_path, ordinal`. The caller supplies at most 256 unique normalized
repository-relative paths per batch. Empty input returns an empty tuple; oversized or
duplicate/invalid input raises `ValueError` before SQL.

This is a read API only. SQLite Schema, Manifest, publication, and retrieval ranking do
not change.

## Scope-Directed Data Flow

```text
load current index + map
  -> validate map source
  -> resolve persisted scope contract
  -> freshness-validate an existing snapshot for that scope
  -> expand required Anchor nodes to owning/child file paths
  -> bounded get_chunks_by_paths batches
  -> bounded get_symbols_by_id batches for returned Chunk symbol IDs
  -> unchanged plan_scope_evidence
  -> mandatory capacity/token/availability preflight
  -> unchanged supplemental search and packing
  -> shared Map write transaction
```

The path expansion uses persisted FactNode ownership. Symbol and file nodes contribute
their path; module nodes contribute direct child file paths; repository fallback uses
the file paths reachable from the contract's required Anchor expansion. Paths are
deduplicated in first structural occurrence order before fixed-size batching.

## Unavailable-Evidence Contract

`plan_scope_evidence` detects that a required Anchor has no representative complete
Chunk and raises:

```text
knowledge_map_evidence_unavailable
exit 3
retry_mode=after_recovery
recovery_action=make_source_indexable_or_select_scope
```

Details contain the scope ID and Anchor fact-node ID only. No source path/text is
required in the public error. Map/source/scope validation and freshness validation of
an existing snapshot retain precedence. The unavailable error then precedes snapshot/
reference capacity and token checks because no amount of capacity can make the
mandatory state available, and it precedes supplemental retrieval. Artifact bytes
remain unchanged.

The deterministic Map continues to include empty/skipped file structures. Enrichment
for a scope without a snapshot continues to return `knowledge_map_evidence_not_found`.

## Compatibility

- Pure planner selection and query-plan hashes remain unchanged when required Chunks
  exist.
- Existing Evidence snapshots and enrichments require no migration.
- The new code/recovery pair is additive to the public Map error matrix and must be
  documented in both locales.
- Snapshot freshness currently uses a global Chunk read; optimizing that adjacent path
  is deferred unless tests prove it is necessary to satisfy the reported direct-
  planning bound.

## Performance Proof

Instrument Store calls and/or SQLite query projections in a repository with many
unrelated files and one small scope. Direct planning performs path-batch Chunk queries
and symbol-ID batch queries only; it performs zero ParseResult and Relationship reads.
The supplemental search's retrieval-owned work is measured separately and not claimed
as eliminated.

## Rollback

The Store API and service optimization can roll back without persisted-data changes.
The unavailable error and paired public contract roll back together before release.
