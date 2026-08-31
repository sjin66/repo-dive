# Correct Knowledge Map Review Findings

## Goal

Restore the Knowledge Map correctness and bounded-work guarantees invalidated by the
post-archive review. Constrained builds must remain structurally valid and preserve
useful Flow inputs, Flow coverage counts must be truthful, and Evidence collection must
avoid repository-wide per-file parse reconstruction while reporting unavailable source
Evidence with actionable behavior.

## Background

Independent review reproduced five defects after the original parent task was archived:

- `src/repo_dive/knowledge_map/lifting.py:173-179` can omit a required `resolves_to`
  edge while retaining a resolved node, causing strict artifact validation to fail and
  the public command to return exit `4` / `knowledge_map_derivation_failed` instead of
  a derivation-budget error.
- The same lexical `(origin, id)` truncation retains derived edges before parser
  `calls`/`imports`, which can reduce known static Flows to root-only records.
- `src/repo_dive/knowledge_map/flows.py:101-106` recounts overlapping unstarted-root
  suffixes after the global candidate budget is exhausted; six terminal roots with
  `flow_budget=1` produce `included=1, omitted=6` instead of `omitted=5`.
- `src/repo_dive/knowledge_map/evidence_service.py:251-259` performs one global Chunk
  read plus one complete three-query `get_parse_result()` per Manifest file, measured
  as `1 + 3N` SELECTs before supplemental retrieval.
- `src/repo_dive/knowledge_map/evidence.py:78-97` classifies a required Anchor without
  any complete Chunk as Evidence capacity exhaustion even though increasing capacity
  cannot recover it.

## Capability Map

| Deliverable | Owning child | Dependency |
|---|---|---|
| Required edge closure and constrained Flow-input selection | `08-31-map-edge-budget-closure` | None |
| Exact Flow candidate omission accounting | `08-31-map-flow-omission-accounting` | None |
| Scope-directed Evidence reads and unavailable-Anchor behavior | `08-31-map-evidence-planning-corrections` | Public unavailable-Evidence decision |

The parent owns the source findings, cross-child compatibility, acceptance review, and
clean-snapshot release proof. Product implementation belongs only to the children.

## Requirements

### KMC-R1: Valid Edge-Budget Behavior

- Every retained resolved reference must retain its exact `resolves_to` trace.
- If mandatory resolution closure alone exceeds the one persisted `edge_budget`, fail
  with exit `3` / `knowledge_map_budget_exceeded`, name `edge_budget`, and write no
  artifact.
- Optional selection under pressure must not let derived aggregate edges starve all
  Flow-relevant parser `calls`/`imports` edges.
- After mandatory resolution closure, spend optional slots on Flow-relevant parser
  `calls`, then parser `imports`, then aggregate and remaining parser edges, using
  stable IDs within each tier.
- Retained edges remain globally bounded and serialized in strict `(origin, id)` order;
  omission accounting remains total candidates minus retained edges.

### KMC-R2: Truthful Flow Coverage

- Count the current traversal frontier and all unstarted roots exactly once at the
  first global work-budget exhaustion point.
- Preserve current deterministic root/queue order, work-budget formula, candidate
  normalization, utility suppression, final Flow limit, and public schema.
- Do not claim an unknowable exact count of terminal descendants behind a discarded
  branching frontier; retain the existing one-frontier-item/one-omission meaning.

### KMC-R3: Scope-Directed Evidence Planning

- Resolve the requested scope before loading planning facts.
- Load complete Chunks only for required-anchor-reachable paths through a bounded,
  stable Store API, then load only referenced Symbols in bounded batches.
- Mandatory planning must not call `get_parse_result()`, construct unrelated
  Relationships, or scale direct-fact queries with total Manifest file count.
- Preserve representative selection, mandatory-before-supplemental preflight, query
  plan identity, Evidence ordering, freshness, and artifact byte behavior.

### KMC-R4: Actionable Missing-Anchor Behavior

- A current required Anchor with no complete indexed Chunk must not return a capacity
  error or recommend increasing capacity.
- Preserve empty/skipped-file deterministic structures and scope IDs; Evidence
  collection must return a dedicated unavailable-source error with an actionable,
  stable public recovery contract.
- Empty and skipped files are supported real fixtures, not malformed-index fixtures.

### KMC-R5: Compatibility And Release

- Keep the exact six-command public Map family, Schema `1.0`, the one total
  `edge_budget`, and the one shared Map writer transaction.
- Bump the deterministic Knowledge Map algorithm version from `1` to `2`; existing
  algorithm-1 artifacts must fail closed through the established rebuild recovery.
- Do not add a model call, dependency, writer, lock, Wiki integration, graph alias, or
  `map status`.
- Update matched English/Chinese documentation for any public error change.
- Preserve existing high-budget deterministic output and index/search/context/Wiki
  behavior.
- Validate the exact allowlisted clean snapshot; ignored Host skills and `.codegraph/`
  remain outside the product change.

## Acceptance Criteria

- [ ] **KMC-AC1:** Insufficient mandatory resolution closure returns the exact budget
  error and no write; exact-boundary and larger constrained builds strictly round-trip.
- [ ] **KMC-AC2:** Constrained selection retains useful parser call/import input without
  exceeding total `edge_budget`, preserves producer order, and reports exact omissions.
- [ ] **KMC-AC3:** Six independent terminal roots with `flow_budget=1` report one
  included and five omitted; boundary and branching-frontier cases count once.
- [ ] **KMC-AC4:** Direct Evidence planning uses bounded scope-directed Chunk/Symbol
  reads, performs no per-file ParseResult reconstruction, and has query-count scaling
  independent of unrelated Manifest files.
- [ ] **KMC-AC5:** Empty/skipped required Anchors return the approved actionable behavior
  before supplemental retrieval and preserve artifact bytes.
- [ ] **KMC-AC6:** Error matrix, precedence, JSON envelope, no-write, path safety, and
  matched documentation tests cover every changed public cell.
- [ ] **KMC-AC7:** Focused correctness/performance suites, `make check`, `make test-unit`,
  `make test-all`, no-gitignore Ruff, help smoke tests, and an independent full-scope
  review pass in an exact clean Python 3.11+ snapshot.

## Out Of Scope

- New user-configurable edge-category budget fields or per-category budgets in Schema
  `1.0`.
- Exact enumeration of terminal Flow descendants after traversal work is discarded.
- Redesign of retrieval ranking or removal of supplemental repository search.
- Native expansion of JS/TS relationship extraction.
- Cleanup of ignored Host integrations or `.codegraph/`.

## Open Questions

None. Missing-Anchor visibility, optional-edge priority, call/import priority, and
algorithm-version compatibility have explicit approved decisions.
