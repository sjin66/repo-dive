# Knowledge Map Flow Accounting Implementation Plan

## F1: Red Tests

- Add 4-, 5-, and 6-root deterministic cases with `flow_budget=1` and
  `nodes_per_flow=1`.
- Add a branched-frontier case proving queued states and unstarted roots are counted
  once.
- Pin exact included/omitted counts and truncation reasons.

## F2: Minimal Correction

- Add one exhaustion flag in `src/repo_dive/knowledge_map/flows.py`.
- Break the outer root loop after the first globally exhausted queue.
- Do not change work-budget calculation, candidate construction, IDs, terminal reasons,
  deduplication, prefix removal, utility handling, or final Flow slicing.

## F3: Verify

- Run Flow, build, view, performance, deterministic replay, and evaluation suites.
- Run `make check` and independent review.
- Confirm no model, schema, CLI, documentation, or algorithm-identity change belongs to
  this child beyond consuming the algorithm version established by the edge child.

## Rollback Gate

If correct counting requires estimating unvisited terminal descendants or changing
public field meanings, return to planning rather than widening this correction.
