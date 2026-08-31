# Fix Knowledge Map Edge Budgeting

## Goal

Make every legal edge budget produce either a strictly valid bounded graph or the
stable derivation-budget failure, while retaining useful parser edges for static Flow
derivation under optional-edge pressure.

## Requirements

- Treat every exact `resolves_to` trace required by a retained resolved node as
  mandatory closure.
- Preflight mandatory resolution-edge count against the single global `edge_budget`.
- Return `knowledge_map_budget_exceeded` with `budget_name=edge_budget`, exit `3`,
  `after_recovery` / `raise_named_budget`, safe diagnostics, and no artifact write when
  closure cannot fit.
- Allocate remaining slots through an explicit deterministic semantic policy rather
  than lexical `origin` ordering, then re-sort the retained set by `(origin, id)`.
- Prioritize Flow-relevant parser `calls`/`imports` before aggregate and remaining
  parser edges; within Flow inputs, prioritize `calls` before `imports`, then use stable
  IDs inside each selected tier.
- Keep total retained edges within `edge_budget` and preserve exact candidate-minus-
  retained omission accounting.
- Preserve high-budget output bytes and all existing model/coverage schemas.
- Bump Knowledge Map algorithm version to `2` so existing algorithm-1 artifacts require
  an explicit rebuild rather than remaining accepted with old constrained behavior.

## Acceptance Criteria

- [ ] A real resolved-reference build with insufficient closure returns the exact
  public budget error instead of exit `4` derivation failure.
- [ ] Exact mandatory-boundary artifacts strictly validate and retain every required
  resolution trace.
- [ ] Constrained call and import fixtures retain Flow-relevant parser occurrences and
  produce non-root-only valid Flows.
- [ ] Edge producer order, total bound, coverage counts, omission reason, idempotence,
  and no-write behavior are pinned.
- [ ] Existing high-budget lifting, Flow, build, and evaluation output remains stable.

## Out Of Scope

- New persisted category-budget fields or independent category limits.
- Downgrading known resolved references to hide omitted closure.
- Treating every parser call/import occurrence as mandatory closure.

## Open Questions

None. The approved policy is mandatory resolution closure, calls, imports, aggregates,
then remaining parser edges, with algorithm version `2`.
