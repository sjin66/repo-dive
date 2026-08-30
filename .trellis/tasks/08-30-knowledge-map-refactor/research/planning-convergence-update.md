# Research Update: Knowledge Map Planning Convergence

- **Date:** 2026-08-30
- **Authority:** User convergence directives, current Trellis task/specs, current source/tests, and repository `AGENTS.md`
- **Comparison material:** `docs/superpowers/specs/2026-08-30-knowledge-graph-prd.md`, `docs/superpowers/specs/2026-08-30-knowledge-graph-design.md`, and `docs/superpowers/plans/2026-08-30-knowledge-graph-implementation.md`

## Active Spec Update

Update: active Trellis backend specs were added after the original research snapshots.
The current active specs listed below supersede the earlier “not found” observations.

- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/repository-classification.md`
- `.trellis/spec/backend/wiki-template-contracts.md`
- `.trellis/spec/backend/tooling-integration-contracts.md`

## Canonical Decisions

- Public naming is Knowledge Map, `repo-dive map`, `repo_dive.knowledge_map`, and `.repo-dive/knowledge-map.json` only.
- The deterministic fact graph is internal. No public `graph` alias or second artifact/package is planned.
- Deterministic map build/show/validate works with empty semantic state. Agent enrichment is optional.
- Version 1 has architecture, static-flow, and reading-tour views only. It has no Wiki topics and changes no Wiki command/schema/template/artifact.
- Public fact nodes are repository, module, file, and symbol. Chunks remain Evidence references because no graph consumer justifies duplicating them as nodes.
- Relationship parser/index Schema upgrade remains a prerequisite because exact per-occurrence call/import/inheritance/containment Evidence cannot be reconstructed safely in the map layer.
- Each syntax occurrence persists independently; traversal and fan-in/fan-out use unique adjacency/neighbors; aggregate edges expose occurrence counts and bounded contributor IDs.
- One repository-local bounded OS advisory lock plus post-lock revision/hash comparison protects all map writers. Atomic replace alone is insufficient for lost-update prevention.
- Build budgets use required `source_fact_budget`, `artifact_byte_budget`, and a strict versioned budget file for all sublimits. Show and Evidence retain explicit result/token budgets.
- Agent prose, labels, and associations are decomposed into claim-level text with claim-owned fact-node, related-node, and Evidence IDs. Validation proves reference validity/ownership/freshness, not entailment.
- Budget fields are classified as derivation, semantic capacity, artifact capacity, or operational; capacity reduction below current use fails without silently dropping semantics.
- Cluster/flow/tour scope expansion, anchor tie-breaks, permission tables, and complete Evidence/enrichment projections are frozen in the deterministic child handoff.
- Identical enrichment replay compares the current scope hash before expected revision; canonical input bytes/hash exclude expected revision and provide persisted capacity usage.
- Map errors retain the existing envelope and use closed `details.retry_mode`/`details.recovery_action` enums plus deterministic precedence.
- No `map status` is planned. Bounded show output exposes identity/counts; validate exposes health.
- `map reset --scope` is planned as the explicit revision-checked correction path for cited Evidence/enrichment.

## Independent Proposal Material Adopted

- Capability/dependency map and tasks limited to about five primary files.
- Strict complete-document Agent submission patterns and independently cited semantic claims.
- Command-level stable error/recovery tables and process tests.
- Fixture-driven component/flow/reading usefulness and incremental/stale-state testing.
- Clear separation between deterministic structure and Agent prose.

## Independent Proposal Material Rejected Or Superseded

- `repo-dive graph`, `repo_dive.knowledge`, `.repo-dive/graph/`, and `.repo-dive/knowledge-graph.json` conflict with canonical naming.
- `wiki_topics` conflicts with the explicit no-Wiki Version 1 boundary.
- Requiring all semantic units before publication conflicts with deterministic-map independent usability.
- Definition/inferred provenance fallback conflicts with exact edge-occurrence requirements.
- Optimistic pre-write hash comparison without a shared lock leaves a TOCTOU/lost-update window.
- Required Evidence budget failure is exit `3` under the current user directive and repository/requested-data classification, not exit `2`.
- Citation presence must not be reported as semantic grounding precision or truth.

## Task Tree

```text
knowledge-map-refactor (parent requirements/integration)
  -> relationship-provenance-index-schema
  -> deterministic-knowledge-map
  -> map-evidence-enrichment
  -> map-cli-docs-evaluation
```

Dependencies are sequential at contract boundaries: relationship facts before deterministic derivation; deterministic model/store before semantics; deterministic and semantic services before final CLI/docs/evaluation.

## Residual Implementation Risks

- Python reference resolution remains conservative and may leave source-root/relative/shadowed references unresolved.
- Sparse non-Python relationship facts limit flow quality and must stay visible in coverage.
- Cross-platform advisory lock behavior requires real contention/release tests.
- Full JSON artifact serialization requires strict byte/count limits and performance fixtures.
- Parser/index Schema changes can regress structural retrieval unless complete scores/order/explanations are pinned.

These are implementation risks with specified tests, not unresolved product decisions.
