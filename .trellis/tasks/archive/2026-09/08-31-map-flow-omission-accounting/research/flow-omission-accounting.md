# Research: Knowledge Map Flow omission accounting

- **Query**: Verify the reported Flow `omitted_count` overcount under global work-budget exhaustion, including the 6 independent roots / `flow_budget=1` reproduction; establish count and truncation semantics; identify the smallest deterministic correction, tests, boundaries, and unresolved decisions.
- **Scope**: internal
- **Date**: 2026-08-31

## Findings

### Files Found

| File Path | Description |
|---|---|
| `.trellis/spec/backend/knowledge-map-contracts.md` | Active deterministic artifact, budget, coverage, and bounded-view contract. |
| `.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/prd.md` | Original requirement for closed Flow rules, deterministic truncation fixtures, and bounded projections. |
| `.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/design.md` | Original Flow traversal and complete omission-metadata design. |
| `.trellis/tasks/archive/2026-08/08-30-map-cli-docs-evaluation/design.md` | Public result metadata intent for included/omitted counts and truncation. |
| `.trellis/tasks/08-31-map-flow-omission-accounting/prd.md` | Child-task goal: correct omitted Flow root accounting under global traversal-budget exhaustion. |
| `src/repo_dive/knowledge_map/flows.py` | Flow candidate traversal, global work budget, omission accounting, deduplication, prefix removal, and final Flow budget. |
| `src/repo_dive/knowledge_map/models.py` | Persisted derivation parameters, coverage counts, `StaticFlow` truncation fields, and artifact consistency checks. |
| `src/repo_dive/knowledge_map/build.py` | Propagates `FlowAnalysis` counts and reasons into persisted `MapCoverage`. |
| `src/repo_dive/knowledge_map/views.py` | Separately applies public `max_results` projection metadata to already-persisted Flows. |
| `tests/unit/knowledge_map/test_flows.py` | Existing cycle, no-root, branch-order, size-limit, and utility-suppression tests. |
| `tests/performance/test_knowledge_map_budget.py` | Existing persisted Flow count upper-bound test with `flow_budget=1`; it does not assert omission accounting. |

### Governing Contracts

- Derivation budgets include the Flow and tour limits and are deterministic inputs (`.trellis/spec/backend/knowledge-map-contracts.md:78-80`). Persisted clusters, Flows, tours, and scope contracts are deterministic projections rather than presentation guesses (`.trellis/spec/backend/knowledge-map-contracts.md:88-90`).
- Views must report explicit included/omitted/truncated metadata (`.trellis/spec/backend/knowledge-map-contracts.md:96-97`), and required tests include Flow ties, cycles, suppression, truncation, and accurate view truncation (`.trellis/spec/backend/knowledge-map-contracts.md:144-151`).
- The archived design says node/edge/cluster/Flow/tour truncation must use deterministic inclusion rules and complete omission metadata (`.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/design.md:29-35`). Flow traversal specifically uses stable queue traversal, cycle avoidance, bounds, utility suppression, exact-sequence deduplication, and no-prefix emission (`.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/design.md:66-70`).
- The archived PRD requires the closed Flow roots, edge set, traversal order, utility rule, budgets, deduplication, and terminal reasons (`.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/prd.md:46-50`) and deterministic truncation fixtures (`.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/prd.md:66-75`).

### Exact Count Meanings

#### Build-time `FlowAnalysis.included_count`

`included_count` is exactly `len(kept)`, where `kept` is the deterministic sort of useful Flow candidates sliced to `flow_budget` (`src/repo_dive/knowledge_map/flows.py:224-250`). These are the Flows returned from derivation and persisted into the artifact (`src/repo_dive/knowledge_map/build.py:60-76,108-110,130-132`). Artifact validation enforces that `coverage.included_flows == len(artifact.flows)` (`src/repo_dive/knowledge_map/models.py:1937-1946`).

#### Build-time `FlowAnalysis.omitted_count`

The implementation computes four additive omission classes (`src/repo_dive/knowledge_map/flows.py:224-248`):

1. `suppressed`: queued traversal states plus not-yet-started roots discarded when the global candidate work budget is exhausted (`flows.py:101-106`);
2. exact-sequence duplicates: `len(candidates) - len(unique)` (`flows.py:224-225,241`);
3. prefix candidates removed by no-prefix emission: `len(unique) - len(useful)` (`flows.py:226-237,241`);
4. useful candidates dropped by the final persisted `flow_budget`: `max(0, len(useful) - len(kept))` (`flows.py:238-244`).

Thus `omitted_count` is not merely “roots not persisted.” It combines discarded traversal-frontier units, materialized candidates removed during normalization, and useful candidates removed by the final Flow limit. For independent terminal roots there is one candidate per root, so the intended total is exact: `included_count + omitted_count == root_count`.

Utility suppression is different: a terminal utility leaf is represented by an included Flow ending before that utility and carrying `suppressed_utility_node_ids` (`flows.py:125-174`; `models.py:858-959`). It adds the global reason `utility_suppressed`, but does not itself increment `omitted_count`. Existing tests pin an included utility-suppressed Flow and the reason (`tests/unit/knowledge_map/test_flows.py:92-104`).

#### Public view `included_count` / `omitted_count`

The Flow view has a second, separate count layer. It receives only persisted `artifact.flows`, slices those records by `max_results`, and reports:

```python
included_count = len(included)
omitted_count = len(all_values) - len(included)
truncated = len(included) < len(all_values)
```

(`src/repo_dive/knowledge_map/views.py:45-51,83-104`). Therefore view `omitted_count` means persisted records hidden by `max_results`; build-time omissions remain in the nested `coverage.omitted_flows`. The CLI documentation confirms that `show` bounds persisted facts rather than recomputing them (`docs/en/cli-contract.md:35-48`).

### Work Budget and Suppressed Roots

- The global traversal budget is derived internally as `flow_budget * max(nodes_per_flow, 1) * 4` (`src/repo_dive/knowledge_map/flows.py:85-89`). The public model requires all derivation parameters to be positive (`src/repo_dive/knowledge_map/models.py:147-175,252-263`), so the `max(..., 1)` is defensive in normal validated builds.
- “Work” is one dequeued traversal state, including each root’s initial one-node state. The check occurs before dequeue and increment (`flows.py:98-108`). It is global across all roots because `work` is initialized before the root loop (`flows.py:89-90`).
- At exhaustion, the intended one-time frontier accounting is `len(queue) + len(roots) - root_index - 1`: all pending states for the current root plus one initial state for each unstarted root (`flows.py:102-105`).
- `flow_depth` and `edges_per_flow` bound individual paths but do not directly scale this work budget; only `flow_budget` and `nodes_per_flow` do (`flows.py:88,111-115`).

### Verified Reproduction

Executed against the current source with six independent symbol roots named `pkg0.main` through `pkg5.main`, no edges, `flow_budget=1`, `flow_depth=3`, `nodes_per_flow=1`, and `edges_per_flow=1`:

```text
{'flow_ids': ['r0'], 'included_count': 1, 'omitted_count': 6,
 'no_roots': False,
 'truncation_reasons': ('candidate_budget', 'flow_budget')}
```

The result is deterministic but overcounts by one. The trace is:

| Event | Work | Candidates | Added to `suppressed` |
|---|---:|---:|---:|
| Roots `r0`…`r3` are each dequeued | 4 | 4 | 0 |
| Before dequeuing `r4`, budget is exhausted | 4 | 4 | `1` queued state + `1` later root = 2 |
| Outer loop nevertheless starts `r5` | 4 | 4 | `1` queued state + `0` later roots = 1 |

Final arithmetic is `suppressed 3 + duplicates 0 + prefixes 0 + final-budget omissions 3 = 6`. The correct independent-root accounting is one kept root plus five omitted roots, so `omitted_count` must be `5`.

The defect is at the loop boundary: `queue.clear(); break` exits only the inner `while queue` loop (`src/repo_dive/knowledge_map/flows.py:101-106`). The outer `for root_index, root in enumerate(roots)` continues, sees the already-exhausted global budget for every subsequent root, and repeatedly recounts overlapping suffixes of the root list.

For `B = work_budget` independent one-step roots and `k = root_count - B > 0`, current `suppressed` becomes `k(k+1)/2` instead of `k`; the overcount is `k(k-1)/2`. The six-root case has `B=4`, `k=2`, and overcount `1`.

### Smallest Deterministic Correction

Preserve all existing root ordering, queue ordering, work-budget calculation, frontier accounting, candidate normalization, IDs, and metadata. Record that the global budget was exhausted at the existing check, then exit the outer root loop immediately after exiting the current root’s queue loop. In structural terms:

```python
work_exhausted = False
for root_index, root in enumerate(roots):
    ...
    while queue:
        if work >= work_budget:
            suppressed += len(queue) + len(roots) - root_index - 1
            truncation_reasons.add("candidate_budget")
            work_exhausted = True
            break
        ...
    if work_exhausted:
        break
```

This is the smallest correction consistent with the current accounting definition: the frontier and all remaining roots are counted exactly once at the first global exhaustion point. It does not redefine a Flow candidate, change the public schema, alter final `flow_budget` selection, or require changes to models, build propagation, or views.

### Deterministic Boundary Cases

1. **No roots**: returns no Flows, both counts zero, `no_roots=True`, and no truncation reasons (`flows.py:63-84`; existing test at `tests/unit/knowledge_map/test_flows.py:48-60`).
2. **Exactly fills work budget**: four independent roots with `flow_budget=1`, `nodes_per_flow=1` consume all four work units but never encounter another queued state. Expected: included `1`, omitted `3`, reason `flow_budget` only.
3. **First over-budget root**: five such roots encounter exhaustion once. Expected: included `1`, omitted `4`, reasons `candidate_budget` and `flow_budget`. Current behavior happens to be correct because no later root remains to be recounted.
4. **Two or more roots beyond budget**: six roots are the smallest failing independent-root case. The correction must keep the first exhaustion’s suffix count and prevent every later recount.
5. **Pending branch frontier**: exhaustion can occur with multiple queued states for the current root. The correction must retain `len(queue)` in the one-time count, not replace it with only a remaining-root count.
6. **Final Flow budget without work exhaustion**: useful candidates may exceed `flow_budget` even when candidate work did not exhaust. `flow_budget` remains the sole reason added at `flows.py:238-244`.
7. **Deduplication and prefix removal**: those omission terms remain independent of work exhaustion and should still be added once (`flows.py:224-242`).
8. **Utility suppression**: the represented Flow remains included with `truncated=False` and `terminal_reason="utility_suppressed"`; its utility node is metadata, not an omitted Flow count (`flows.py:131-173`).
9. **Per-Flow truncation versus global truncation**: `StaticFlow.truncated` describes an included Flow cut by depth/size (`flows.py:111-124,191-213`), while `candidate_budget` is only a global coverage omission reason propagated by build (`build.py:83-114`). No candidate-budget `StaticFlow` is currently emitted even though the model enum accepts that terminal reason (`models.py:897-905`).

### Recommended Tests

The smallest regression test belongs in `tests/unit/knowledge_map/test_flows.py` beside the existing derivation tests:

- construct six independently ranked `*.main` roots with no edges;
- derive with `flow_budget=1`, `nodes_per_flow=1`, and positive depth/edge limits;
- assert the retained root is the first deterministic root;
- assert `included_count == 1`, `omitted_count == 5`, and reasons equal `("candidate_budget", "flow_budget")`.

Useful boundary assertions in the same parameterized test are four roots (`omitted=3`, no `candidate_budget`) and five roots (`omitted=4`, candidate budget present). A branched-root case can additionally pin that a multi-item current queue plus all unstarted roots are counted once. The existing performance assertion only proves `len(artifact.flows) <= flow_budget` (`tests/performance/test_knowledge_map_budget.py:37-53,162-176`) and cannot detect this count defect.

If propagation needs explicit coverage, a focused build-level assertion can verify `artifact.coverage.included_flows`, `omitted_flows`, and `omission_reasons`; the propagation itself is direct at `src/repo_dive/knowledge_map/build.py:83-114` and artifact validation already closes included count to persisted Flows (`models.py:1937-1946`).

### External References

None. This is an internal deterministic loop/accounting defect; no external library behavior is involved.

### Related Specs

- `.trellis/spec/backend/knowledge-map-contracts.md:78-97` — deterministic budgets, persisted projections, and explicit view metadata.
- `.trellis/spec/backend/knowledge-map-contracts.md:134-153` — required Flow suppression/truncation fixtures and accurate view truncation tests.
- `.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/design.md:29-35,66-70` — complete omission metadata and stable Flow traversal rules.
- `.trellis/tasks/archive/2026-08/08-30-deterministic-knowledge-map/prd.md:46-50,66-76` — closed Flow derivation and truncation acceptance requirements.

## Caveats / Unresolved User-Owned Decisions

1. **Meaning of a suppressed frontier item**: under branching, one discarded queue state may eventually yield zero, one, or multiple terminal Flow candidates. Current code treats each discarded frontier state as one omitted unit. The one-time outer-loop correction preserves that existing definition; redefining `omitted_count` as the unknowable exact number of terminal descendants would require a broader contract decision.
2. **`utility_suppressed` as an omission reason**: current behavior includes the shortened Flow, leaves its `truncated` flag false, increments no omission count, but adds a global truncation/omission reason. Whether that vocabulary should change is separate from the reported overcount.
3. **Unused per-Flow `candidate_budget` terminal reason**: the model accepts it, but global exhaustion emits no partial `StaticFlow`; only coverage receives `candidate_budget`. Emitting partial Flows would be a behavior/schema-semantics decision and is not needed for the smallest correction.
4. **Public view versus build coverage counts**: current contracts expose both meanings in one show response (projection omission at the top level, derivation omission under coverage). Renaming or further documenting them would be a public-contract decision, not part of the loop fix.
