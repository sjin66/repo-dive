# Knowledge Graph PRD

**Status:** Draft for review
**Date:** 2026-08-30
**Product:** repo-dive CLI
**Related design:** `2026-08-30-knowledge-graph-design.md`
**Related implementation plan:** `../plans/2026-08-30-knowledge-graph-implementation.md`

## 1. Executive Summary

repo-dive will add a repository-owned Knowledge Graph workflow that turns the existing symbol and relationship index into four evidence-grounded views:

1. an architecture map;
2. executable or request-oriented flows;
3. a guided reading path;
4. Wiki topic hints.

The deterministic CLI owns source facts, graph construction, evidence packaging, validation, freshness, and artifact persistence. The calling agent owns semantic labels, summaries, and explanations. The CLI must not invoke a generative model.

This feature is additive. It does not replace the private SQLite index, retrieval, Evidence, or governed Wiki Schema 2.0 workflow.

## 2. Problem Statement

repo-dive already knows many low-level facts: files, symbols, containment, imports, calls, inheritance, chunks, and retrieval scores. Those facts are useful for search, but they are not yet a durable model of how a repository is organized.

An agent that receives only search results must repeatedly infer:

- which modules form a coherent component;
- which components depend on each other;
- where important runtime flows begin and end;
- which files should be read first;
- which facts support a generated architectural statement;
- whether a previously generated explanation is stale.

This repeated inference makes documentation less consistent, harder to resume, and difficult to validate. A public, versioned Knowledge Graph closes that gap without moving probabilistic generation into the CLI.

## 3. Product Goal

Enable a calling agent to produce DeepWiki-level repository explanations from a deterministic, resumable, evidence-backed graph contract.

Success means that two runs over the same index and the same accepted semantic inputs produce byte-stable graph artifacts, while every agent-generated semantic statement remains traceable to current repository Evidence.

## 4. Users and Jobs to Be Done

### 4.1 Primary users

- Coding agents that need a bounded, machine-readable map before answering repository questions.
- Maintainers generating architecture and onboarding documentation.
- Reviewers validating whether generated documentation is supported by source code.
- Tool authors consuming repo-dive JSON contracts.

### 4.2 Core jobs

- "Show me the repository's major components and their dependencies."
- "Trace the important execution or data flows with source locations."
- "Give me a sensible reading order for understanding this repository."
- "Provide structured topics that can improve a Wiki without allowing the model to invent its hierarchy."
- "Tell me what became stale after the source index changed."

## 5. Product Principles

1. **Facts before semantics.** Parser and index facts are never rewritten by an agent.
2. **Evidence before prose.** Semantic content is accepted only with valid Evidence IDs.
3. **Deterministic core.** Identical inputs produce identical ordering, IDs, hashes, and outputs.
4. **Explicit generation boundary.** The CLI packages context; the calling agent generates prose.
5. **Resumable stages.** Fact initialization, Evidence collection, semantic submission, validation, and publication are separately persisted.
6. **Bounded work.** Potentially large operations require explicit node, edge, result, or token budgets.
7. **Conservative freshness.** Stale semantic content is never silently published as current.
8. **Additive compatibility.** Existing `index`, `context`, and `wiki` commands retain their current behavior.

## 6. Scope

### 6.1 In scope for Version 1

- A new non-interactive `repo-dive graph` command family.
- A deterministic fact graph derived from the published index.
- Repository, file, and symbol nodes.
- Containment, import, call, inheritance, and derived component-dependency edges when supported by the index.
- Deterministic component candidates based on repository topology and indexed relationships.
- Deterministic flow candidates rooted in supported entrypoint signals.
- Per-unit Evidence snapshots under explicit token budgets.
- Strict, evidence-cited semantic submissions from the calling agent.
- Architecture, flow, reading-tour, and Wiki-topic projections.
- Staleness detection and safe incremental reuse.
- A stable current artifact under `.repo-dive/knowledge-graph.json`.
- JSON and Markdown command responses that follow the existing CLI contract.

### 6.2 Out of scope for Version 1

- A browser dashboard or interactive graph visualizer.
- A graph database or network service.
- Implicit LLM or embedding-provider calls.
- Cross-repository or organization-wide graphs.
- Agent-created parser facts or source relationships.
- Automatic replacement of the governed Wiki hierarchy.
- Automatic page prose generation.
- Arbitrary graph query languages.
- New language-parser coverage solely for the Knowledge Graph.
- Exact call-site provenance where the current parser/index does not expose it; Version 1 must label fallback provenance precision explicitly.

## 7. Functional Requirements

### KG-R1: Deterministic fact initialization

`graph init` must read through supported index interfaces, build a bounded fact graph, derive semantic work units, persist resumable state, and return a summary. It must not read private SQLite tables directly from the Knowledge Graph domain.

### KG-R2: Explicit graph budgets

`graph init` must require positive node and edge budgets. If facts are omitted, the artifact must record `truncated: true`, exact included counts, known omitted counts, and deterministic truncation reasons. It must never omit facts silently.

### KG-R3: Stable identity and ordering

Public node, edge, unit, Evidence, and projection IDs must be deterministic. Collections must have documented stable sort keys. Wall-clock timestamps must not affect semantic identity or content hashes.

### KG-R4: Fact provenance

Every fact edge must record its origin (`parser` or `derived`), confidence, and a repository-relative source locator when available. The locator must state whether its line precision is `exact`, `definition`, or `inferred`.

### KG-R5: Semantic work units

The CLI must expose independently resumable units for components, flows, and the repository reading tour. Each unit has an explicit state: `pending`, `evidence_ready`, `generated`, `stale`, or `failed`.

### KG-R6: Evidence collection

`graph evidence` must package complete source chunks for one unit under an explicit token budget. Required Evidence must be reserved before supplemental Evidence. If required Evidence cannot fit, the command must fail without persisting a misleading snapshot.

### KG-R7: Agent submission

`graph unit` must accept a strict JSON document through a file or stdin. It must validate the unit ID, schema version, Evidence IDs, referenced fact node IDs, semantic relationship endpoints, allowed heading/content rules, source identity, and request hash before changing state.

### KG-R8: Idempotence

Submitting an identical payload for an already generated unit must succeed without changing the artifact. Reusing the same unit intent with different semantic content must fail with a stable validation error unless an explicit future regeneration workflow is introduced.

### KG-R9: Validation

`graph validate` must verify schema validity, referential integrity, state transitions, Evidence freshness, source identity, projection consistency, truncation metadata, and deterministic ordering. It must not repair invalid input silently.

### KG-R10: Publication

`graph build` must publish `.repo-dive/knowledge-graph.json` atomically only after every required unit is generated and validation succeeds. A failed build must preserve the last valid artifact.

### KG-R11: Status and recovery

`graph status` must report current index identity, graph state, unit counts by status, truncation, last valid artifact identity, and the next valid operations. It must not require source prose to be re-generated when the underlying referenced facts and Evidence remain unchanged.

### KG-R12: Projections

The published graph must include:

- `architecture`: components, membership, responsibilities, and dependency edges;
- `flows`: ordered steps linked to fact nodes and Evidence;
- `reading_tour`: ordered repository scopes with rationale and prerequisites;
- `wiki_topics`: evidence-backed topic hints and relevant files.

The `wiki_topics` projection is advisory in Version 1. It must not mutate Wiki Schema 2.0 structures or bypass template contracts.

### KG-R13: CLI behavior

All functional commands must be non-interactive and support `--format json`. JSON mode emits exactly one document on stdout, diagnostics on stderr, no ANSI codes, and the repository-wide exit-code mapping.

### KG-R14: Locality and security

All graph data remains local by default. Paths must be validated against the selected repository root. Diagnostics must not include full source chunks, secrets, access tokens, or environment dumps.

### KG-R15: Compatibility

The release must be additive:

- no change to existing `repo-dive index`, `context`, or `wiki` behavior;
- no change to current Wiki artifacts;
- no requirement that existing repositories create a Knowledge Graph;
- an independent Knowledge Graph schema version.

## 8. Required Workflow

```text
index
  -> graph init
  -> graph evidence --unit <unit-id>
  -> calling agent generates a semantic unit
  -> graph unit --input <unit.json>
  -> repeat until complete
  -> graph validate
  -> graph build
```

The context-to-generate boundary is between `graph evidence` and `graph unit`.

## 9. Acceptance Criteria

### AC-1: Determinism

- Given the same published index, budgets, locale, and semantic submissions, two complete workflows produce byte-identical `knowledge-graph.json` files.
- Node, edge, unit, and projection order remains stable across runs.

### AC-2: Evidence grounding

- Every agent-authored summary and semantic relationship contains at least one valid Evidence ID.
- Removing or altering a referenced Evidence record causes validation to fail.

### AC-3: No implicit generation

- Unit and integration tests prove that graph commands do not instantiate or call a generative-model provider.
- The CLI can complete fact initialization and Evidence collection offline.

### AC-4: Safe budgets

- Initialization without node and edge budgets exits `2`.
- Evidence collection without a token budget exits `2`.
- Truncated graphs expose included and omitted counts in JSON and in the final artifact.

### AC-5: Resume and freshness

- Re-running `graph init` against the same index is idempotent.
- After a source/index change, only units whose referenced facts or Evidence changed become stale.
- A stale graph cannot be published.

### AC-6: Atomicity

- A validation or write failure leaves the previous `knowledge-graph.json` unchanged.
- A successful build replaces it atomically.

### AC-7: CLI contract

- Every graph command returns one valid JSON result document in JSON mode.
- Validation, repository/input, and internal failures map to exit codes `2`, `3`, and `4` respectively.
- All Evidence paths are repository-relative POSIX paths with one-based inclusive lines.

### AC-8: Compatibility

- Existing unit and integration tests for index, retrieval, context, and Wiki pass unchanged.
- Existing Wiki output does not depend on the presence of Knowledge Graph artifacts.

### AC-9: Projection integrity

- Every architecture member, flow step, reading-tour item, and Wiki topic references existing graph nodes or units.
- Projection validation rejects dangling, cyclic-where-forbidden, or stale references.

### AC-10: Documentation

- English and Simplified Chinese CLI documentation describe the same commands, fields, recovery actions, and constraints.
- Agent workflow documentation marks the graph generation boundary explicitly.

## 10. Product Metrics and Evaluation

Version 1 is evaluated with repository fixtures rather than production telemetry.

- **Grounding precision:** 100% of semantic claims contain valid Evidence references.
- **Structural validity:** 100% of published edges and projections pass referential-integrity checks.
- **Determinism:** 100% byte equality across repeat-run fixtures.
- **Recovery:** stale-source and interrupted-workflow fixtures preserve the last valid artifact.
- **Coverage:** the published artifact reports fact and source-file coverage, including truncation.
- **Usefulness:** fixture expectations verify that known components and known flows appear without introducing unsupported ones.

No usage analytics or source-content telemetry is added.

## 11. Product Decisions

1. The public Knowledge Graph is a projection of the private index, not a replacement for it.
2. Agent semantics are stored separately from parser facts and cannot mutate them.
3. Version 1 uses deterministic topology and manifest/path signals; it does not add a graph database or community-detection dependency.
4. The published artifact is advisory to Wiki Schema 2.0. Automatic Wiki integration requires a separate approved design.
5. Partial graphs are allowed only under explicit budgets and must remain visibly truncated.
6. Missing exact edge locations are represented with lower provenance precision, never presented as exact call sites.

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Symbol IDs change after line movement | Semantic units become unnecessarily stale | Unit identities derive from stable repository scopes; fact-to-index IDs remain explicit references |
| Parser relationship coverage varies by language | Some flows appear incomplete | Record coverage and provenance precision; never infer unsupported edges as parser facts |
| Large repositories exceed useful context size | Agent receives shallow or partial context | Require graph and token budgets; generate and resume per unit |
| Agent submits plausible but unsupported semantics | Published graph becomes misleading | Require Evidence IDs and validate every referenced fact and semantic edge |
| New workflow drifts from Wiki contracts | Duplicate or conflicting architecture | Keep Wiki projection advisory in Version 1 and retain template ownership |
| Incremental reuse accepts stale semantics | Incorrect documentation survives source changes | Hash unit membership and Evidence snapshots; invalidate conservatively |

## 13. Open Questions Requiring Approval

The following are deliberate review gates, not implementation blockers for this draft:

1. Should Version 1 publish only JSON, or also a deterministic Markdown overview?
2. Should exact call-site provenance be promoted into the index schema in Version 1 or deferred?
3. After Version 1 proves stable, should governed Wiki Evidence consume `wiki_topics` automatically or only behind an explicit flag?

Until approved otherwise, the implementation specification assumes JSON publication, definition-level fallback provenance, and no automatic Wiki consumption.
