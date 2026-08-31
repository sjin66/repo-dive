# Knowledge Map Edge Budget Design

## Ownership

`knowledge_map.lifting` owns candidate classification because it simultaneously knows
the resolved-node closure, all generated edge categories, and effective `edge_budget`.
Strict artifact validation remains a defensive backstop. The CLI does not translate
this defect; it receives the typed domain budget error.

## Selection Algorithm

Build all candidate categories as today, then partition without changing their values:

```text
mandatory = resolution edges
optional tier 1 = parser calls
optional tier 2 = parser imports
optional tier 3 = aggregate derived edges
optional tier 4 = remaining parser edges
```

Each category is sorted by edge ID. If `len(mandatory) > edge_budget`, raise
`knowledge_map_budget_exceeded` with:

```json
{
  "budget_name": "edge_budget",
  "provided": "<edge_budget>",
  "required": "<mandatory_count>",
  "retry_mode": "after_recovery",
  "recovery_action": "raise_named_budget"
}
```

Numeric detail types must follow the existing budget helper's executable contract.
Otherwise append deterministic tier prefixes until the remaining capacity is zero.
Finally sort the selected set by `(origin, id)` for strict persistence.

`omitted_edges` remains the full candidate count minus selected count. The
`edge_budget` omission reason remains present exactly when this value is nonzero.

## Algorithm Identity

Set `KNOWLEDGE_MAP_ALGORITHM_VERSION = "2"`. Strict readers reject version `1` through
the existing invalid-artifact recovery path. Build may replace an old artifact through
the established invalid/current snapshot transaction; no migration or dual decoder is
introduced.

## Compatibility

- Schema `1.0`, budget fields, IDs, edge records, producer order, coverage fields, and
  writer protocol remain unchanged.
- Unconstrained candidate sets remain identical apart from algorithm-bound hashes.
- Constrained outputs intentionally change to preserve closure and Flow utility.
- Calls rank before imports because runtime edges are stronger than structural fallback.

## Test Design

Unit fixtures cover insufficient mandatory closure, exact closure, multiple traces,
category priority, producer order, and omission accounting. Build/process fixtures
prove exit `3`, no write, algorithm-1 rejection/rebuild, valid non-root-only call/import
Flows, deterministic replay, and high-budget compatibility.

## Rollback

Selection and algorithm version form one rollback unit. Reverting only one would make
artifact identity misrepresent behavior.
