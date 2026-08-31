# Knowledge Map Edge Budget Implementation Plan

## E1: Red Tests

- Add a minimal exact resolved-reference lifting fixture where mandatory closure exceeds
  `edge_budget`; assert the typed budget error and exact details.
- Add exact-boundary and multiple-resolution fixtures proving strict closure.
- Add constrained calls/imports fixtures that currently retain only derived edges and
  produce root-only Flows.
- Add a public process regression proving the current exit `4` behavior is wrong.

## E2: Implement Deterministic Selection

- Refactor only the edge selection block in `src/repo_dive/knowledge_map/lifting.py`.
- Preflight resolution closure with the existing budget error pattern.
- Select calls, imports, aggregates, and remaining parser edges by stable tier/ID.
- Re-sort retained edges by `(origin, id)` and preserve omission counts.

## E3: Bump Algorithm Identity

- Change the Knowledge Map algorithm version constant to `2`.
- Update exact model/build fixtures and public documentation that names the algorithm.
- Add algorithm-1 invalid/rebuild recovery coverage; add no compatibility shim.

## E4: Verify

Run focused lifting, models, build, Flow, store, command, error, recovery, performance,
evaluation, and bilingual repository-contract suites. Run `make check` and the clean
snapshot gates required by the parent before child review.

## Review And Rollback Gate

An independent checker must prove closure, total bounds, producer ordering, category
priority, no-write errors, and high-budget compatibility. Any need for a new budget
field or model shape returns the child to planning.
