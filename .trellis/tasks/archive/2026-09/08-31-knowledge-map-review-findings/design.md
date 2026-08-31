# Knowledge Map Review Corrections Design

## Boundary

This parent coordinates three independently testable corrections. It owns no product
implementation. The children retain existing package ownership:

| Concern | Owner | Required boundaries |
|---|---|---|
| Edge selection and algorithm version | deterministic Knowledge Map child | lifting, models/build compatibility, public budget process proof |
| Flow omission accounting | deterministic Knowledge Map child | pure Flow derivation and build coverage propagation |
| Evidence read scaling and unavailable Anchors | indexing + Evidence child | typed Store query, Evidence planning/service, public error/docs |

The shared artifact remains Schema `1.0`, with one global edge budget and one shared
writer transaction. Algorithm version `2` is the compatibility boundary for the
changed deterministic edge-selection policy. The Flow accounting correction changes
coverage content but requires no separate identity bump.

## Cross-Child Contracts

### Deterministic Build

Edge selection has two phases. Mandatory `resolves_to` edges are preflighted first. If
they cannot fit, lifting raises the existing derivation-budget error. Remaining slots
are selected by semantic tiers:

1. parser `calls`;
2. parser `imports`;
3. aggregate derived edges;
4. remaining parser edges.

Stable edge ID breaks ties inside each tier. The retained set is finally sorted by the
strict producer key `(origin, id)`. Selection never exceeds the single persisted
`edge_budget`, and coverage continues to report all generated candidates minus the
retained set.

Algorithm version `2` makes every algorithm-1 artifact unsupported through existing
strict decoding. Recovery remains rebuild; no in-place migration or compatibility
reader is added.

### Flow Coverage

Global candidate-work exhaustion is a one-time event. The current queue and every
unstarted root are added once to `suppressed`, then both traversal loops terminate.
Candidate deduplication, prefix removal, utility suppression, and final `flow_budget`
omissions remain separate additive terms.

### Evidence Collection

Collection validates repository, index, map source, and scope existence before direct
fact loading. If that scope already has an Evidence snapshot, its persisted references
are freshness-validated before replacement planning so an unavailable Anchor cannot
conceal stale Evidence. Required Anchors are expanded to a deterministic set of
repository paths:

- symbol and file Anchors load their owning file;
- module Anchors load all direct child files in stable path/ID order;
- repository fallback loads the anchor-reachable file set defined by the persisted
  contract, not an unconstrained Manifest scan.

`IndexStore.get_chunks_by_paths()` accepts a bounded unique path batch, returns complete
Chunks ordered by `(file_path, ordinal)`, returns an empty tuple for empty input, and
rejects invalid, duplicate, or more than 256 paths before SQL. The service uses fixed
batches of at most 256.
It batches the returned non-null Chunk `symbol_id` values through the existing
`get_symbols_by_id()` API. The pure planner receives the same complete per-path facts
and retains all existing tie rules.

Supplemental retrieval remains unchanged and may perform its retrieval-owned global
read only after mandatory preflight succeeds. Existing snapshot freshness validation
is not widened in this correction.

### Unavailable Evidence

A required Anchor with no complete indexed Chunk raises:

```text
code: knowledge_map_evidence_unavailable
exit: 3
retry_mode: after_recovery
recovery_action: make_source_indexable_or_select_scope
```

Details contain only bounded scope/Anchor identifiers. The deterministic Map, scope,
and artifact bytes remain unchanged. Empty/skipped-file structures remain visible.
The error is command-specific to `map evidence`; enrich without a snapshot retains
`knowledge_map_evidence_not_found`. It follows map/source/scope and existing-snapshot
freshness failures, but precedes snapshot/reference capacity, token preflight, and
supplemental retrieval because none can make the required source available.

## Compatibility

- Existing algorithm-1 artifacts require `map build`; no automatic rewrite occurs.
- Schema, budget document, commands, scope permissions, Evidence snapshot fields, and
  writer protocol do not change.
- High-budget algorithm-2 derivation must retain the same facts/order as the corrected
  full candidate set; only algorithm identity and affected constrained/coverage output
  change.
- English and Chinese CLI/workflow documentation must add equivalent unavailable-
  Evidence recovery text.
- Wiki remains independent and consumes neither Map artifacts nor the new error.

## Rollback

- Flow accounting can revert independently because it changes no schema or identity.
- Evidence query optimization and unavailable error revert together only before the
  public error is shipped; artifact state is unchanged either way.
- Algorithm version `2` and edge selection revert together. Once algorithm-2 artifacts
  are published, rollback requires rebuilding them with a compatible implementation.

## Verification

Each child receives an independent review and archive. Parent completion then validates
the integrated exact snapshot, every changed public error cell, all six commands,
compatibility suites, matched docs, and clean-tree scope.
