# Fix Knowledge Map Flow Accounting

## Goal

Ensure persisted Flow coverage never double-counts discarded roots after the global
candidate work budget is exhausted.

## Requirements

- Stop outer-root traversal after the first global budget exhaustion.
- Count the current queue and all not-yet-started roots exactly once.
- Preserve deterministic root and queue ordering, work-budget calculation, duplicate
  and prefix omission accounting, final Flow-budget selection, utility behavior, IDs,
  schema, and view projection semantics.
- Preserve the existing bounded approximation that one discarded frontier item is one
  omitted unit; do not infer terminal descendants that were never traversed.

## Acceptance Criteria

- [ ] Six independent roots with `flow_budget=1` and `nodes_per_flow=1` produce
  `included_count=1`, `omitted_count=5`, and exactly candidate/Flow budget reasons.
- [ ] Four-root exact-work and five-root first-over-budget boundaries retain correct
  counts and reasons.
- [ ] A branched current queue plus unstarted roots is counted once.
- [ ] Deduplication, prefix removal, utility suppression, included Flow truncation, and
  build coverage propagation remain unchanged.

## Out Of Scope

- Redefining omissions as exact unknown terminal descendants.
- Emitting new partial Flows for global candidate exhaustion.
- Renaming public build-coverage or view-projection count fields.

## Open Questions

None. The smallest correction preserves the existing accounting contract.
