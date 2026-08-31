# Research: Existing deterministic fact graph and graph analytics

- **Query**: Inspect the existing repo-dive implementation and tests relevant to a deterministic fact graph, graph lifting/ranking/clustering/flow detection; verify cited capability claims and identify reusable models/services and missing capabilities.
- **Scope**: internal
- **Date**: 2026-08-30

## Update: Active Trellis Specs

Update: active Trellis backend specs were added after this research snapshot.
The current active specs listed below supersede the earlier “not found” observation.

- `.trellis/spec/backend/index.md` identifies the active backend contracts.
- `.trellis/spec/backend/repository-classification.md` governs immutable published-index snapshots, bounded manifest/path signals, stable ordering, and safe observations reused by deterministic map analysis.
- `.trellis/spec/backend/wiki-template-contracts.md` is a negative ownership boundary: Version 1 Knowledge Map must not alter governed Wiki structure, `wiki init`, or Wiki Schema 2.0.
- `.trellis/spec/backend/tooling-integration-contracts.md` governs repository-owned path closure, allowlisted staging, and clean-snapshot verification.

Historical “no `.trellis/spec/**/*.md`” lines below describe the repository at the original research time and are not current planning authority.

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/repo_dive/parsing/models.py` | Immutable `Chunk`, `Symbol`, `Relationship`, and `ParseResult` fact contracts plus stable identity factories. |
| `src/repo_dive/parsing/python_ast.py` | Python symbol and `contains`/`imports`/`calls`/`inherits` relationship extraction. |
| `src/repo_dive/parsing/tree_sitter.py` | JavaScript/TypeScript class/function/method extraction and `contains` edges. |
| `src/repo_dive/parsing/pipeline.py` | Deterministic parser-result normalization, deduplication, splitting, and ordering. |
| `src/repo_dive/indexing/schema.sql` | SQLite Schema 4 tables and constraints for symbols and relationships. |
| `src/repo_dive/indexing/store.py` | Typed persistence and bounded relationship queries. |
| `src/repo_dive/indexing/graph.py` | Stable symbol lookup and explicitly bounded breadth-first traversal. |
| `src/repo_dive/retrieval/structural.py` | Symbol-match and relationship-path scoring for source-chunk retrieval. |
| `src/repo_dive/retrieval/fusion.py` | Deterministic weighted reciprocal-rank fusion across lexical, structural, and optional vector channels. |
| `src/repo_dive/classification/models.py` | Versioned, immutable repository classification contracts. |
| `src/repo_dive/classification/service.py` | Deterministic rule scoring for primary type, topology, and facets. |
| `tests/unit/parsing/test_python_ast.py` | Extraction, source range, relationship-kind, and determinism coverage. |
| `tests/unit/indexing/test_graph.py` | Symbol matching, direction, cycles, depth, confidence, node/edge budgets, and stable traversal coverage. |
| `tests/unit/retrieval/test_structural.py` | Relationship expansion and explainable structural-score coverage. |
| `tests/unit/classification/test_service.py` | Stable topology/facet scoring, fallback, ordering, and serialization coverage. |

### Code Patterns

#### Existing fact layer

The repository already has a deterministic **symbol graph**, not a generalized repository fact graph:

```python
@dataclass(frozen=True, slots=True)
class Relationship:
    source_id: str
    target_id: str
    kind: str
    confidence: float
    source: str
```

`Chunk`, `Symbol`, `Relationship`, and `ParseResult` are immutable tuples/dataclasses (`src/repo_dive/parsing/models.py:12-66`). Chunk IDs include path, one-based inclusive range, content hash, and optional symbol ID; symbol IDs include path, kind, qualified name, and range (`src/repo_dive/parsing/models.py:77-134,166-172`). Relationship confidence is constrained to `[0,1]` (`src/repo_dive/parsing/models.py:137-154`).

Python extraction creates module/class/function/method symbols and exact definition chunks (`src/repo_dive/parsing/python_ast.py:46-75,78-137`). It emits:

- `contains` at confidence `1.0` (`src/repo_dive/parsing/python_ast.py:126-134`)
- `imports` at confidence `1.0` (`src/repo_dive/parsing/python_ast.py:180-195`)
- `inherits` and `calls`, resolving same-file definitions at `1.0` and unresolved/reference targets at `0.75` (`src/repo_dive/parsing/python_ast.py:165-172,196-217`)

JS/TS Tree-sitter extraction currently creates module/class/function/method symbols and only `contains` edges (`src/repo_dive/parsing/tree_sitter.py:134-216`). Plain-text fallback creates chunks only (`src/repo_dive/parsing/text.py:29-46`). Therefore graph coverage is language- and parser-dependent.

The parsing pipeline deduplicates by stable IDs/edge keys and sorts every result deterministically (`src/repo_dive/parsing/pipeline.py:46-65,69-117`).

#### Existing graph persistence and traversal

SQLite Schema 4 stores `symbols` and `relationships` with foreign keys, confidence checks, a primary key over `(source_id,target_id,kind,source)`, and source/target indexes (`src/repo_dive/indexing/schema.sql:13-26,41-51,81-93`). Each relationship also has a `file_path` owner and per-file ordinal.

`IndexStore` already satisfies the narrow `GraphReader` protocol (`src/repo_dive/indexing/graph.py:41-62`) through:

- exact/case-folded symbol lookup in stable source order (`src/repo_dive/indexing/store.py:428-464`)
- bounded ID lookup (`src/repo_dive/indexing/store.py:466-477`)
- incoming/outgoing/both edge queries, optional kind filtering, confidence threshold, stable SQL ordering, and limit (`src/repo_dive/indexing/store.py:479-529`)

`SymbolGraph.neighbors` performs bounded BFS with direction, depth, edge-kind, node, edge, and confidence controls; it tracks truncation and returns endpoint-enriched `GraphEdge` values (`src/repo_dive/indexing/graph.py:20-38,65-208`). This is reusable graph-access behavior.

#### Existing ranking

Structural ranking is query-rooted rather than graph-global. Exact and normalized symbol matches receive fixed scores; traversed path scores multiply edge confidence and divide by `path_length + 1` (`src/repo_dive/retrieval/structural.py:116-162,228-237`). Results preserve textual relationship paths including direction, kind, confidence, and provenance (`src/repo_dive/retrieval/structural.py:165-225`).

Repository search combines BM25, symbol-graph structural retrieval, and optional vectors; candidate counts and graph expansion are bounded (`src/repo_dive/retrieval/service.py:21-24,51-128`). Weighted RRF is stable and explainable, with source-order tie breakers and overlap deduplication (`src/repo_dive/retrieval/fusion.py:18-69,82-194,197-254,303-380`). This is evidence ranking, not node centrality or architecture ranking.

Classification is a second deterministic derivation layer. It scores versioned path/language/manifest signals into one primary repository type, one topology (`single_project`, `monorepo`, or `microservices`), and ordered facets (`src/repo_dive/classification/models.py:15-19,139-213`; `src/repo_dive/classification/service.py:38-95`). It does not consume the symbol graph; it consumes an immutable indexed-file snapshot (`src/repo_dive/classification/adapter.py:24-70`).

### Claim Verification

| Claim implied by task wording | Verified status | Evidence |
|---|---|---|
| A deterministic fact graph already exists. | **Partly correct.** A deterministic persisted symbol/relationship graph exists. There is no generalized fact ontology for files, packages, components, flows, clusters, architecture views, or semantic claims. | `src/repo_dive/parsing/models.py:25-47`; `src/repo_dive/indexing/schema.sql:13-51` |
| Graph traversal exists. | **Correct.** It is bounded, deterministic BFS over typed symbol edges. | `src/repo_dive/indexing/graph.py:89-208` |
| Graph ranking exists. | **Correct only for query-rooted evidence ranking.** Structural path scores and weighted RRF exist; repository-wide node importance/centrality does not appear in source or tests. | `src/repo_dive/retrieval/structural.py:116-162`; `src/repo_dive/retrieval/fusion.py:82-194` |
| Graph lifting exists. | **Not found.** No symbol-to-file/package/component graph lifting implementation or persisted lifted-node schema was found. Classification is repository-level rule scoring, not graph lifting. | Global source search; classification input at `src/repo_dive/classification/adapter.py:24-70` |
| Graph clustering exists. | **Not found.** No community detection, SCC condensation, or clustering model/service/test was found. | Global source/test search for cluster/community/SCC |
| Flow detection exists. | **Not found as a derived capability.** Raw `calls`, `imports`, `contains`, and `inherits` edges plus path traversal exist, but no entrypoint-to-sink flow model, detector, state, or view exists. | `src/repo_dive/parsing/python_ast.py:165-256`; `src/repo_dive/indexing/graph.py:89-208` |
| Architecture and reading-path views exist. | **Not found.** Wiki templates ask the agent to write architecture/flow prose, but no deterministic architecture-view or ordered reading-path artifact exists. | `src/repo_dive/wiki/templates/resources/en/primary/developer_tool.md:2-23`; global source search |

### Compatibility-Aligned Boundary Map

The existing source boundaries establish the following natural ownership for the requested capability:

| Concern | Existing boundary to reuse | Contract implication |
|---|---|---|
| Source facts and stable identities | `parsing.models` and parser adapters | Keep repository-relative POSIX paths and one-based inclusive ranges; retain deterministic identity derivation. |
| Fact persistence and current-generation identity | `indexing.store`, `indexing.manifest`, `indexing.service` | Any index-resident fact changes participate in SQLite schema and build-parameter compatibility. |
| Bounded graph access | `indexing.graph` and its `GraphReader` protocol | Graph operations remain persistence-independent and explicitly budgeted. |
| Query ranking | `retrieval.structural`, `retrieval.fusion`, `retrieval.service` | Existing scores are evidence scores and should not be conflated with graph-global ranking values. |
| Repository-level deterministic taxonomy | `classification` package | Existing pattern for versioned rule registries, immutable snapshots, strict decoding, and auditable matched signals. |
| Public views/artifacts | command modules plus Wiki service/store | CLI owns argument/I/O only; services own derivation; stores own atomic persistence. |

The smallest coherent capability boundary visible from existing code is: consume the current immutable symbol graph, derive a deterministic bounded graph result tied to the current index identity, and expose that result without changing existing search semantics. Clustering, generalized semantic enrichment, multiple rendered views, and Wiki prose generation are separate capabilities because no current contract joins them.

### Likely Test Locations

- `tests/unit/parsing/`: new deterministic fact extraction and stable identity cases, following `test_python_ast.py` and `test_tree_sitter.py`.
- `tests/unit/indexing/test_store.py`: schema, round-trip, foreign-key, corruption, and read-only behavior.
- `tests/unit/indexing/test_graph.py`: lifting/traversal inputs, stable ordering, cycles, budgets, and provenance.
- A graph-derivation unit-test module adjacent to its domain package for ranking/clustering/flow behavior; no current equivalent exists.
- `tests/integration/test_index_command.py`: observable counts/schema/version and idempotent generation behavior.
- `tests/performance/test_index_scaling.py` and `tests/performance/test_retrieval_budget.py`: corpus scaling and bounded graph work.
- `evals/cases/`: graph-derived ranking heuristics require evidence-grounding evaluation coverage under repository rules; current cases cover indexing/search/context/Wiki, not knowledge maps.

## External References

None. This request was an internal implementation audit.

## Related Specs

- No `.trellis/spec/**/*.md` files were found; `.trellis/spec/` currently contains no discoverable Markdown contracts.
- `docs/en/architecture.md:24-26,65,88-120,137-154` documents evidence identity, bounded graph traversal, replaceable protocols, ranking, generation publication, and recovery boundaries.
- `AGENTS.md` defines source-module boundaries and requires deterministic core behavior, explicit budgets, stable evidence locations, and no implicit generative model call.

## Caveats / Not Found

- There is no implementation or test containing PageRank, centrality, SCC, community detection, graph clustering, lifted component nodes, explicit flow objects, or reading-path objects.
- Cross-file Python references are represented as line-local reference symbols unless resolved within the same parsed file (`src/repo_dive/parsing/python_ast.py:211-240`); this constrains repository-wide call-graph interpretation.
- JS/TS structural extraction does not emit call/import/inheritance edges (`src/repo_dive/parsing/tree_sitter.py:173-216`). Other languages and syntax-error fallback may have chunks but no symbols or relationships.
- `pyproject.toml:13-18` has no graph-analysis runtime dependency; current graph algorithms use Python collections and SQLite.
