# Research: Knowledge Map edge-budget closure and Flow priority

- **Query**: Verify required `resolves_to` closure truncation and derived-edge priority starving parser `calls`/`imports`; determine invariants, error ownership, compatible budget semantics, smallest alternatives, tests, and decisions.
- **Scope**: internal
- **Date**: 2026-08-31

## Findings

### Files Found

| File Path | Description |
|---|---|
| `.trellis/spec/backend/knowledge-map-contracts.md` | Active closure, budget, error, and public process contracts. |
| `.trellis/tasks/archive/2026-08/08-30-knowledge-map-refactor/design.md` | Parent budget classification and essential-closure design. |
| `.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/{prd.md,design.md}` | Archived child requirements for endpoint closure, bounded truncation, resolution traceability, and Flows. |
| `src/repo_dive/knowledge_map/lifting.py` | Produces aggregate, resolution, and parser edges, then globally truncates them. |
| `src/repo_dive/knowledge_map/models.py` | Enforces edge ordering, endpoint/resolution/Flow closure, coverage counts, and the total edge bound. |
| `src/repo_dive/knowledge_map/flows.py` | Builds Flow adjacency exclusively from parser `calls`/`imports`. |
| `src/repo_dive/knowledge_map/build.py` | Calls lifting, downstream analyses, artifact construction, and reports edge omissions. |
| `src/repo_dive/commands/map.py` | Preserves typed domain errors but converts unexpected artifact-construction failures to exit-4 `knowledge_map_derivation_failed`. |
| `tests/unit/knowledge_map/test_lifting.py` | Current occurrence/aggregate and ambiguous-resolution tests; no low-edge-budget resolved case. |
| `tests/unit/knowledge_map/test_flows.py` | Current direct Flow tests; edges are supplied directly and bypass lifting budgets. |
| `tests/unit/knowledge_map/test_build.py` | Current lifecycle tests use `edge_budget=3000`; no constrained-edge build. |
| `tests/performance/test_knowledge_map_budget.py` | Asserts broad persisted bounds with `edge_budget=100`; no category or closure pressure. |
| `tests/integration/test_map_errors.py` | Public matrix expects `knowledge_map_budget_exceeded` exit 3 and `knowledge_map_derivation_failed` exit 4, but its budget-exceeded fixture only lowers `node_budget`. |

### Exact Invariants

1. **One resolved node requires one retained resolution trace.** `FactNode` requires a resolved reference to carry exactly one candidate and a rule (`models.py:608-615`). Artifact validation then requires at least one `resolves_to` edge from that node, the exact candidate target set, and the same rule (`models.py:1751-1767`). This is required reference closure, not optional output.
2. **All retained edges share one global bound.** Schema 1.0 contains only `edge_budget` (`models.py:147-175`, `203-250`), and artifact validation checks `len(artifact.edges) <= derivation.edge_budget` (`models.py:2111-2117`). Coverage separately requires `included_edges == len(edges)` (`models.py:1937-1940`). Therefore `edge_budget` denotes the maximum total retained edge count across all origins/kinds.
3. **Optional category allocation may only partition that total.** An internal deterministic priority or quota can allocate slots inside `edge_budget`, but retained categories cannot each receive an additional independent `edge_budget`. New user-configurable category quotas are not Schema-1.0-compatible: the budget decoder requires the exact field set (`models.py:228-250`, `265-278`), and the parent requires every effective derivation field to be persisted (`08-30-knowledge-map-refactor/design.md:223-236`).
4. **Required closure that cannot fit must be a domain budget failure.** The active matrix says required node/edge closure failure is `knowledge_map_budget_exceeded` with no write (`knowledge-map-contracts.md:99-115`) and public source/derivation capacity failures are exit 3, never required-state truncation (`knowledge-map-contracts.md:388-399`). The archived design says essential endpoint closure fails instead of producing dangling facts (`08-30-deterministic-knowledge-map/design.md:29-35`).
5. **Artifact model validation is the defensive backstop, not budget classification ownership.** Lifting is the first boundary that knows the complete mandatory resolution-edge set and the caller's edge budget (`lifting.py:166-179`). It already owns essential node-budget classification and raises `RepositoryError("knowledge_map_budget_exceeded", ...)` (`lifting.py:83-97`). Build should receive a closed `LiftedGraph`; model validation should continue rejecting malformed artifacts.
6. **Flows require retained parser occurrences.** Flow adjacency ignores every derived edge and every non-`calls`/`imports` parser edge (`flows.py:47-63`). Each persisted Flow must point to retained edges and representative relationship contributors (`models.py:1730-1750`). Aggregate edges cannot substitute without changing the current Flow contract.
7. **Final edge producer order remains `(origin, id)`.** Strict artifacts reject any other persisted order (`models.py:1616-1621`). Selection priority can differ from serialization order, but the selected set must be re-sorted by the producer key before artifact construction.
8. **Omission accounting is total generated minus total retained.** Lifting currently records `len(ordered_edges) - len(included_edges)` (`lifting.py:184-196`), and build maps this to coverage plus the `edge_budget` omission reason (`build.py:83-113`). A category-aware selector can preserve this public accounting without a schema change.

### Defect Path 1: Required Resolution Closure Becomes Exit 4

Current code constructs all categories and applies one lexical prefix:

```python
ordered_edges = tuple(
    sorted((*aggregates, *resolution_edges, *parser_edges),
           key=lambda item: (item.origin, item.id))
)
included_edges = ordered_edges[: parameters.edge_budget]
```

(`lifting.py:166-180`)

Because every resolution edge has `origin="derived"` (`lifting.py:222-250`), it competes lexicographically with aggregate edges. A resolved node is persisted before edge truncation (`lifting.py:110-149`), so dropping its `resolves_to` edge produces a graph that lifting reports as usable but `KnowledgeMapArtifact.create()` rejects as `resolved reference traceability is inconsistent` (`models.py:1751-1767`). `KnowledgeMapBuildService.build()` does not translate this value error (`build.py:52-133`); `_handle_build()` catches it as unexpected and emits `knowledge_map_derivation_failed` (`commands/map.py:122-145`), which is exit 4 according to the public matrix (`tests/integration/test_map_errors.py:157-161`).

### Reproduction Evidence

Two minimal reproductions were run without changing repository files.

1. A handcrafted one-file snapshot with `main -> reference(app.run)`, one exact `app.run` definition, and `edge_budget=1` retained one derived aggregate and omitted three edges. The reference node remained `resolution_status="resolved"`; direct artifact construction raised:

```text
ValueError: resolved reference traceability is inconsistent
```

2. A real temporary repository containing `helper.py: run` and `app.py: from helper import run; main() -> run()`, indexed through `IndexService` and built through public `repo_dive.cli.main`, reproduced end to end:

```text
exit 4
error knowledge_map_derivation_failed
artifact_exists False
```

Thus the no-write property happens to hold, but the stable owner/code/exit contract does not.

### Defect Path 2: Derived Prefix Starves Flow Edges

String ordering puts `"derived" < "parser"`, so every aggregate and resolution edge sorts before every parser occurrence (`lifting.py:173-180`). Each ordinary relationship can create both file- and module-level aggregate edges (`lifting.py:253-304`), making parser starvation possible even at nontrivial budgets.

A real temporary one-file repository with `main() -> helper()` and `edge_budget=2` built successfully with:

```text
retained origins: [derived, derived]
retained kinds:   [contains, calls]
omitted_edges:    5
Flow steps:       [1]
terminal_reason:  terminal
```

The parser `calls` occurrence was omitted, so Flow analysis saw a named root but no outgoing adjacency and persisted a root-only terminal Flow. This follows directly from `flows.py:51-63,108-124`; the source call exists in the index but cannot participate after lifting truncation.

### Existing Test Gap

- `test_lifting_keeps_occurrences_separate_and_aggregates_counts` uses `edge_budget=100` (`test_lifting.py:15-39,42-104`).
- The only resolution lifting test is ambiguous and correctly expects no `resolves_to` edge (`test_lifting.py:106-176`); it cannot exercise mandatory resolved closure.
- Flow unit tests inject parser edges directly (`test_flows.py:20-104,186-207`) and therefore cannot observe lifting priority.
- Build tests use `edge_budget=3000` (`test_build.py:182-206`).
- The integration budget error sets `node_budget=1`, not `edge_budget` (`test_map_errors.py:366-367`), so the matrix does not prove edge-closure ownership.
- The performance budget fixture uses `edge_budget=100` and only checks broad Flow/tour/artifact bounds (`test_knowledge_map_budget.py:37-73,162-186`).

### Smallest Contract-Compatible Alternatives

| Alternative | Behavior | Compatibility / tradeoff |
|---|---|---|
| **A. Mandatory closure, then explicit semantic tiers** | Preflight all `resolution_edges`; fail if they exceed `edge_budget`. Spend remaining slots on parser `calls`/`imports`, then other optional categories; re-sort retained edges by `(origin, id)`. | Smallest local change in lifting; preserves one total edge budget, model/coverage schema, and Flow's parser provenance. Absolute Flow priority may omit more architecture aggregates under pressure. |
| **B. Mandatory closure, then deterministic balanced allocation** | Preflight resolution closure; divide remaining slots between Flow parser edges and aggregates (fixed split or round-robin), then other parser edges. | Protects both architecture and Flow signals, but policy is more complex, tiny budgets need tie rules, and a fixed quota becomes algorithm behavior that must be pinned. User-configurable quotas would require schema/decoder/docs/revision changes. |
| **C. Treat all Flow-relevant parser edges as required** | Fail with `knowledge_map_budget_exceeded` unless all resolution plus parser `calls`/`imports` fit. | Strongest Flow completeness and simplest failure semantics, but conflicts with the established allowance for deterministic edge truncation and can reject large occurrence inventories where a useful partial artifact is expected. |
| **D. Keep lexical truncation but downgrade resolved nodes when their edge is omitted** | Change selected resolved references to unresolved/omitted state. | Avoids invalidity but discards a known exact resolution because of edge selection, weakens resolution traceability, and does not address parser starvation; it is not compatible with the stated required-closure invariant. |

### Recommended Design Determination

Alternative A is the narrowest behavior consistent with the existing contracts:

1. Compute all candidate categories as today.
2. Define `resolution_edges` as mandatory closure.
3. If `len(resolution_edges) > edge_budget`, raise `RepositoryError` with code `knowledge_map_budget_exceeded`, `budget_name="edge_budget"`, `recovery_action="raise_named_budget"`, and `retry_mode="after_recovery"`; publish nothing.
4. Use the remaining global slots for deterministic optional tiers, with parser `calls`/`imports` before aggregates so Flow inputs cannot be starved by derived-edge lexical ordering; retain stable ID ordering within each tier.
5. Use any leftover slots for remaining parser kinds.
6. Re-sort the selected set by `(origin, id)` before returning it, preserving strict producer order.
7. Keep `omitted_edges = total_candidate_edges - retained_edges` and the existing `edge_budget` omission reason.

This design does not add category budgets and never permits more than `edge_budget` total retained edges. Untruncated builds retain the same full edge set and producer order; constrained builds intentionally select a different valid subset.

### Tests Needed

1. **Lifting closure failure**: one exact resolved reference with `edge_budget < required_resolution_edges`; assert typed `knowledge_map_budget_exceeded`, exact edge-budget details, and no partial `LiftedGraph`.
2. **Exact closure boundary**: budget exactly equals required resolution count; assert all resolved nodes have exact `resolves_to` traces, optional omissions are counted, and `KnowledgeMapArtifact.create()` succeeds.
3. **Multiple mandatory traces**: several resolved references with IDs arranged on both sides of aggregate IDs; prove behavior is independent of hash lexicography.
4. **Flow priority through lifting**: constrained direct `calls` fixture where aggregates exceed remaining capacity; assert a parser call survives and Flow has at least two steps with matching representative relationship ID.
5. **Import priority**: equivalent constrained `imports` case; assert structural import fallback metadata remains valid.
6. **Producer order**: selected-by-tier edges are finally ordered by `(origin, id)` and strict artifact round-trip succeeds.
7. **Total budget and accounting**: assert `len(edges) <= edge_budget`, `included_edges == len(edges)`, `omitted_edges == all_candidates - len(edges)`, and omission reason is present iff nonzero.
8. **Public process regression**: cross-file exact-reference fixture with insufficient edge closure returns exit 3 / `knowledge_map_budget_exceeded`, exact recovery fields, safe stderr, and no artifact write (replacing the observed exit 4).
9. **Successful constrained build**: public build with enough mandatory closure plus one Flow slot produces a valid persisted artifact and non-root-only call/import Flow.
10. **Compatibility**: high-budget existing lifting/Flow fixture output remains unchanged; repeated constrained builds are byte-preserving.

### Unresolved User-Owned Decisions

1. **Optional-slot policy**: absolute `calls`/`imports` priority (Alternative A) versus a balanced aggregate/Flow allocation (Alternative B). The contract fixes mandatory resolution closure and the global total, but does not specify this tie policy.
2. **Algorithm version**: whether this deterministic selection-policy correction retains algorithm version `"1"` or bumps `KNOWLEDGE_MAP_ALGORITHM_VERSION`. A bump makes existing artifacts unsupported until rebuilt (`models.py:14-16,1481,1540`); retaining it minimizes compatibility impact, while constrained output still changes deterministic revision because persisted edges change.
3. **Priority between `calls` and `imports`**: one combined stable-ID tier versus calls-first then imports. Flow semantics distinguish runtime calls from structural import fallback (`models.py:887-926`), but no active contract ranks one above the other under the global edge budget.

### External References

None. This is governed by repository-owned schema, derivation, and CLI contracts.

### Related Specs

- `.trellis/spec/backend/knowledge-map-contracts.md:69-97` — deterministic closure, budgets, and projections.
- `.trellis/spec/backend/knowledge-map-contracts.md:99-118` — required closure failure and no-write error matrix.
- `.trellis/spec/backend/knowledge-map-contracts.md:388-405` — public exit and recovery behavior.
- `.trellis/tasks/archive/2026-08/08-30-knowledge-map-refactor/design.md:223-236` — global persisted budget semantics and essential endpoint closure.
- `.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/prd.md:34-50,66-75` — resolution/lifting and Flow acceptance criteria.

## Caveats / Not Found

- No active or archived document defines a category quota or an ordering between aggregate edges and Flow-relevant parser edges; only the one total `edge_budget` is normative.
- No existing test exercises an exact resolved reference under edge-budget pressure or a Flow after lifting-level parser starvation.
- The handcrafted closure reproduction proves the exact model invariant; the cross-file temporary repository additionally proves the public exit-4 path end to end.
- Research made no product-code or test changes.
