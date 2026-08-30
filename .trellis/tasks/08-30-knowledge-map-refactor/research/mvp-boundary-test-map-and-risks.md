# Research: Smallest coherent MVP boundary, test map, and major risks

- **Query**: Identify the smallest coherent MVP boundary, recommended module boundaries, likely test locations, and major risks for deterministic knowledge-map work, based only on existing repository contracts.
- **Scope**: internal
- **Date**: 2026-08-30

## Update: Active Trellis Specs

Update: active Trellis backend specs were added after this research snapshot.
The current active specs listed below supersede the earlier “not found” observation.

- `.trellis/spec/backend/index.md` identifies the active backend contracts.
- `.trellis/spec/backend/repository-classification.md` supplies the deterministic snapshot/signal precedent.
- `.trellis/spec/backend/wiki-template-contracts.md` supplies the no-Wiki-change ownership boundary.
- `.trellis/spec/backend/tooling-integration-contracts.md` supplies clean staged-snapshot and repository-owned closure requirements.

The task has since been split into four independently planned children; the parent PRD/design and `planning-convergence-update.md` supersede the original single-task implementation boundary.

## Findings

### Files Found

| File Path | Description |
|---|---|
| `AGENTS.md` | Authoritative product, source-package, CLI, artifact, and verification boundaries. |
| `docs/en/architecture.md` | Current package/data-flow/index/retrieval/Wiki architecture. |
| `src/repo_dive/parsing/models.py` | Smallest reusable source-fact contract. |
| `src/repo_dive/indexing/graph.py` | Smallest reusable graph-reader/traversal contract. |
| `src/repo_dive/indexing/service.py` | Published-index identity and generation lifecycle. |
| `src/repo_dive/classification/models.py` | Example of a separate versioned deterministic derived contract. |
| `src/repo_dive/classification/service.py` | Example of pure derivation over an immutable index snapshot. |
| `src/repo_dive/wiki/submission.py` | Example of strict untrusted agent input validation. |
| `src/repo_dive/wiki/validation.py` | Example of current-index freshness validation. |
| `src/repo_dive/wiki/assembler.py` | Example of pure deterministic view assembly. |
| `tests/unit/indexing/test_graph.py` | Existing graph correctness boundary. |
| `tests/integration/test_cli_io.py` | Public machine-contract boundary. |
| `tests/integration/test_wiki_workflow.py` | Persisted workflow/recovery boundary. |

### Smallest Coherent MVP Boundary

The task goal names five separable capabilities: deterministic facts, graph derivation, agent semantic enrichment, multiple views, and Wiki integration. Existing code only provides complete contracts for the first capability and parts of the others. The smallest coherent boundary that can stand alone under current contracts is:

1. Read the current validated published index without mutation.
2. Reuse persisted `Symbol` and `Relationship` facts, including confidence and provenance.
3. Produce one deterministic, bounded, versioned derived graph document tied to `repository_fingerprint`, `index_build_id`, and SQLite schema version.
4. Preserve stable source evidence (`path`, one-based inclusive lines, symbol/chunk IDs) on every exposed derived item.
5. Keep the result separate from agent prose and existing Wiki state.

This boundary is coherent because all five inputs/identity rules already exist (`src/repo_dive/parsing/models.py:12-66`; `src/repo_dive/indexing/service.py:91-103,560-609`; `src/repo_dive/indexing/graph.py:20-62`). It does not claim clustering, flow detection, architecture rendering, reading paths, or semantic enrichment that the repository does not currently implement.

An agent semantic round trip is a second independently testable boundary: strict schema -> Evidence ownership/freshness -> validated semantic records -> atomic persistence. Wiki projection is a third boundary because Wiki currently consumes page/subsection/Evidence models rather than generic graph data (`src/repo_dive/wiki/models.py:139-354`; `src/repo_dive/wiki/service.py:526-802`).

### Compatibility-Aligned Module Boundaries

These are the module responsibilities implied by existing repository conventions:

| Responsibility | Existing precedent | Boundary rule |
|---|---|---|
| Fact models and identity | `parsing.models` | Immutable typed records; deterministic IDs; source locations remain one-based and repository-relative. |
| Fact extraction | parser adapters + `parsing.pipeline` | No I/O inside adapters; normalize/deduplicate/order after extraction. |
| Physical graph storage | `indexing.store` + `indexing.schema.sql` | SQLite is private; strict schema version; transactional per-document replacement; foreign-key validation. |
| Published index snapshot | `indexing.service.PublishedIndex` | Consumers use the validated current generation read-only. |
| Graph derivation | `indexing.graph` precedent | Narrow reader protocol; explicit direction/depth/node/edge budgets; stable traversal results. |
| Deterministic derived models | `classification.models` precedent | Independent schema/classifier/algorithm version; strict decoder; no timestamps in reproducibility identity. |
| Agent semantic input | `wiki.submission` precedent | Exact schema fields, caller-owned content only, bounded size, typed safe errors. |
| Provenance/freshness | `EvidenceRef`/`EvidenceSnapshot` + `wiki.validation` | Bind claims to current content hash/path/range and current index identity. |
| View rendering | `wiki.assembler` precedent | Pure assembly after validation; rendering does not perform retrieval or mutate domain state. |
| Public command | `commands/*` + `cli.py` | Arguments/formatting only; one JSON envelope; diagnostics to stderr; established exit codes. |
| Artifact persistence | index generations or `WikiStore` precedent | Repository-confined `.repo-dive/` path, complete-document atomic replacement, preserve last valid artifact. |

### Exact Reusable Contracts

- `Chunk`, `Symbol`, `Relationship`, `ParseResult`, and `create_*` factories (`src/repo_dive/parsing/models.py:12-154`).
- `GraphEdge`, `GraphTraversal`, `GraphReader`, `SymbolGraph`, `RelationshipDirection` (`src/repo_dive/indexing/graph.py:12-208`).
- `IndexStore.query_symbols`, `get_symbols_by_id`, `query_relationships`, `get_chunks`, `get_parse_result` (`src/repo_dive/indexing/store.py:428-594`).
- `PublishedIndex` and `load_published_index` current-generation validation (`src/repo_dive/indexing/service.py:91-103,560-609`; public loader is used at `src/repo_dive/retrieval/service.py:65`).
- `ClassificationResult` style of independent schema/algorithm/taxonomy identity and strict decode (`src/repo_dive/classification/models.py:15-19,139-264`).
- `EvidenceRef`, `EvidenceSnapshot`, `RetrievalParameters` (`src/repo_dive/wiki/models.py:44-187`).
- `PageSubmission` strict-input pattern (`src/repo_dive/wiki/submission.py:14-106`).
- Canonical JSON serializer (`src/repo_dive/schema.py:76-86`).
- Atomic repository-owned write primitives (`src/repo_dive/storage/atomic.py`) and strict complete-document store pattern (`src/repo_dive/wiki/store.py:30-131`).

### Missing Capability Inventory

| Capability | Current status |
|---|---|
| General fact ontology beyond symbols/relationships/chunks | Not found. |
| Cross-file canonical symbol resolution | Not found; unresolved Python targets become source-line reference symbols. |
| File/package/component graph lifting | Not found. |
| Graph-global importance/centrality | Not found. |
| SCC/community clustering | Not found. |
| Entrypoint and flow detection | Not found. |
| Architecture/flow/reading-path typed view models | Not found. |
| Generic validated semantic-claim input | Not found. |
| Semantic enrichment persistence/freshness schema | Not found. |
| Knowledge-map CLI command | Not found. |
| Knowledge-map repository artifact | Not found. |
| Knowledge-map-specific evaluations | Not found under `evals/cases/`. |

### Test Map

| Capability/contract | Existing test home or closest precedent |
|---|---|
| Fact identity, one-based ranges, confidence | `tests/unit/parsing/test_models.py`, `test_python_ast.py`, `test_tree_sitter.py` |
| Parser determinism and fallback | `tests/unit/parsing/test_pipeline.py`, `test_python_ast.py`, `test_tree_sitter.py` |
| SQLite schema/round-trip/integrity | `tests/unit/indexing/test_store.py` |
| Graph cycles/direction/budgets/stable order | `tests/unit/indexing/test_graph.py` |
| Structural path scores and explanations | `tests/unit/retrieval/test_structural.py` |
| Stable derived classification contract | `tests/unit/classification/test_models.py` if added; current closest files are `test_service.py`, `test_adapter.py`, `test_registry.py` |
| Manifest/version/public counts | `tests/unit/indexing/test_manifest.py`, `tests/integration/test_index_command.py` |
| Public JSON/stdout/stderr/exit behavior | `tests/unit/test_cli.py`, `tests/unit/test_cli_errors.py`, `tests/integration/test_cli_io.py` |
| Path confinement/untrusted input | `tests/integration/test_security.py` |
| Atomic failure and recovery | `tests/unit/storage/test_atomic.py`, `tests/integration/test_recovery.py` |
| Agent payload validation | `tests/integration/test_wiki_page.py` |
| Evidence freshness/index concurrency | `tests/integration/test_wiki_evidence.py`, `tests/integration/test_wiki_workflow.py` |
| Governed Wiki projection | `tests/integration/test_governed_wiki_quality.py`, `tests/unit/wiki/test_assembler.py` |
| Bounded scaling | `tests/performance/test_index_scaling.py`, `tests/performance/test_retrieval_budget.py` |
| Retrieval/agent quality | new cases beside `evals/cases/indexing.jsonl`, `retrieval.jsonl`, `wiki_evidence.jsonl`, and `wiki_workflow.jsonl` |

### Major Risks (Observed Contract Mismatches or Capability Limits)

1. **Graph coverage differs by language.** Python emits four edge kinds; JS/TS emits only containment; fallback parsers emit no graph facts (`src/repo_dive/parsing/python_ast.py:165-256`; `src/repo_dive/parsing/tree_sitter.py:173-216`; `src/repo_dive/parsing/text.py:29-46`).
2. **Reference identity is not repository-canonical.** Unresolved Python references include local path and source line in their symbol ID (`src/repo_dive/parsing/python_ast.py:229-240`; `src/repo_dive/parsing/models.py:107-134`), so equivalent external/cross-file names can be distinct nodes.
3. **Current “ranking” has different semantics.** Structural/RRF scores rank query evidence, not architectural importance (`src/repo_dive/retrieval/structural.py:116-162`; `src/repo_dive/retrieval/fusion.py:82-194`).
4. **Private SQLite changes are compatibility events.** Consumers require exact Schema 4 and no in-place migration path is exposed (`src/repo_dive/indexing/store.py:619-626`).
5. **Current manifest does not expose graph membership/checksums.** It records aggregate relationship counts and file-to-chunk membership, not graph artifact identity (`src/repo_dive/indexing/manifest.py:61-114,117-186`).
6. **Wiki validation proves provenance ownership, not semantic entailment.** It checks current Evidence, citation ownership, and required direct coverage (`src/repo_dive/wiki/submission.py:80-106`; `src/repo_dive/wiki/validation.py:33-72`).
7. **No current multi-view consistency contract exists.** Architecture, flow, Wiki, and reading-path outputs have no shared typed model or version identity in source.
8. **Budgets are mandatory repository behavior.** Existing graph and retrieval APIs cap depth/nodes/edges/results; an unbounded repository-wide derivation would violate current operational conventions (`src/repo_dive/indexing/graph.py:89-106`; `src/repo_dive/retrieval/service.py:21-24,60-67`).
9. **Documentation version drift exists.** `docs/en/architecture.md:145` names Wiki Schema `1.0`, while implementation and workflow docs use `2.0` (`src/repo_dive/wiki/models.py:21-22`; `docs/en/wiki-workflow.md:61-66`).
10. **No Trellis layer specs are present.** No `.trellis/spec/**/*.md` file was found, so repository-wide `AGENTS.md`, executable behavior, tests, and current docs are the available contract sources.

## External References

None. This request was an internal implementation audit.

## Related Specs

- No `.trellis/spec/**/*.md` files were found.
- `AGENTS.md` is the authoritative repository-wide instruction set.
- `docs/en/architecture.md:40-65,86-120,135-154` describes current package and persistence boundaries.
- `docs/en/development.md:123-126,149-187` describes test/evaluation locations and operational budgets.

## Caveats / Not Found

- Historical note: the PRD contained only a one-line goal when this research snapshot was produced. The converged `prd.md`, `design.md`, and `implement.md` are now authoritative for planned scope.
- The capability inventory is based on source/test/document searches performed on 2026-08-30; no external design proposal was evaluated.
