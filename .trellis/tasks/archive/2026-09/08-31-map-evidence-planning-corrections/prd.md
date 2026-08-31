# Fix Knowledge Map Evidence Planning

## Goal

Make mandatory Evidence planning scale with the selected scope rather than repository
file count, and replace the unrecoverable missing-Anchor capacity response with an
accurate actionable contract.

## Requirements

- Resolve the requested persisted scope before planning-fact loading.
- Add a bounded stable IndexStore query for complete Chunks from a batch of
  repository-relative file paths, ordered by `(file_path, ordinal)`.
- Expand required Anchors to only the paths needed by the existing symbol/file/module
  fallback rules; load referenced Symbols through bounded `get_symbols_by_id` batches.
- Do not call `get_parse_result()` or load unrelated Relationships during direct
  mandatory planning.
- Preserve existing representative ordering, deduplication, anchor accumulation,
  query-plan hashes, mandatory preflight, supplemental retrieval, and persisted
  Evidence shape.
- Treat an existing required Anchor without a complete indexed Chunk as source
  availability, not token/reference capacity.
- Preserve the deterministic cluster/flow/tour structures and scope IDs for empty or
  skipped files. Add a dedicated public unavailable-Evidence error rather than
  filtering those structures.

## Acceptance Criteria

- [ ] Store tests prove bounded path batches, stable ordering, exact path confinement,
  empty input, invalid bounds, and multi-batch equivalence.
- [ ] An N-file repository with a one-file scope performs no ParseResult or Relationship
  reads for direct planning and direct query count does not grow with unrelated files.
- [ ] Existing cluster/flow/tour fallback, ordering, preflight-before-search,
  idempotence, and freshness tests remain green.
- [ ] Real empty and skipped required Anchors produce the approved public behavior,
  safe bounded details, exit `3` where applicable, no supplemental retrieval, and no
  artifact mutation.
- [ ] Any public error change has complete process-matrix, precedence, recovery, spec,
  and matched EN/zh-CN documentation coverage.

## Out Of Scope

- Removing supplemental search's existing retrieval-owned global read.
- Changing Evidence snapshot schema or scope permission tables.
- Using unrelated fallback Chunks for a required fact.

## Open Questions

None. The approved behavior preserves deterministic visibility and extends the public
error contract for unavailable mandatory Evidence.
