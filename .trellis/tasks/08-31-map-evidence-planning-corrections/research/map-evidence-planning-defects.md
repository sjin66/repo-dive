# Research: Knowledge Map Evidence planning defects

- **Query**: Verify the redundant per-file Evidence index reads and the missing-required-anchor misclassification; identify the smallest batch/page and scope-directed loading shape; compare compatible missing-anchor behavior.
- **Scope**: internal
- **Date**: 2026-08-31

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/repo_dive/knowledge_map/evidence_service.py:64-135` | Collection order, global fact loading, mandatory preflight, supplemental search, and capacity checks. |
| `src/repo_dive/knowledge_map/evidence_service.py:251-259` | `_load_facts`: one all-Chunk read followed by one `get_parse_result` call per Manifest file. |
| `src/repo_dive/knowledge_map/evidence.py:45-127` | Pure planner and the current missing-anchor error. |
| `src/repo_dive/knowledge_map/evidence.py:130-191` | Exact symbol/file/module representative-Chunk fallback rules. |
| `src/repo_dive/indexing/store.py:428-477` | Existing bounded symbol lookups, including `get_symbols_by_id`. |
| `src/repo_dive/indexing/store.py:615-710` | Existing file/Chunk-ID page APIs, three-query `get_parse_result`, and global `get_chunks`. |
| `src/repo_dive/indexing/schema.sql:13-39` | Symbols and Chunks are independently queryable by `file_path`; source order is the file-local `ordinal`. |
| `src/repo_dive/retrieval/service.py:51-128` | Supplemental search independently performs another global `get_chunks` read. |
| `src/repo_dive/knowledge_map/lifting.py:50-87` | Every indexed Manifest file, including a file with no Chunks, becomes a file fact. |
| `src/repo_dive/knowledge_map/topology.py:27-107` | Every file fact participates in directory clusters. |
| `src/repo_dive/knowledge_map/flows.py:326-419` | Cluster members, flow steps, and tour targets become required scope anchors. |
| `src/repo_dive/knowledge_map/models.py:1778-1811` | Schema 1.0 requires scope contracts to cover every cluster/flow/tour exactly and pins their exact anchors. |
| `tests/unit/knowledge_map/test_evidence.py:18-148` | Current representative selection/order/deduplication coverage; no missing-Chunk case. |
| `tests/unit/knowledge_map/test_flows.py:107-166` | Current exact scope-anchor assertions. |
| `tests/integration/test_map_evidence_enrichment.py:143-167` | Mandatory token preflight must occur before supplemental retrieval. |
| `tests/performance/test_knowledge_map_budget.py:37-72` | Existing Evidence performance test bounds output/artifact size, but not SQL query/object reads. |
| `tests/integration/test_map_errors.py:169-239` | Frozen public error/recovery mappings and command applicability. |
| `docs/en/cli-contract.md:75-79` and `docs/zh-CN/cli-contract.md` | Public Evidence error table; paired documentation must remain equivalent. |

### Defect 1: exact redundant-read path

`KnowledgeMapEvidenceService.collect` loads the current artifact and then calls `_load_facts` before resolving the requested scope (`evidence_service.py:64-88`). `_load_facts` does this:

```python
chunks = index.get_chunks()
for entry in manifest_files:
    symbols.extend(index.get_parse_result(entry.path).symbols)
```

`get_chunks()` issues one global Chunk query (`indexing/store.py:703-710`). Each `get_parse_result(path)` then issues three queries—Symbols, Chunks, and Relationships—and constructs one complete `ParseResult` (`indexing/store.py:669-701`). For `N` Manifest files, planning therefore issues exactly `1 + 3N` SELECTs before supplemental retrieval:

- one global Chunk SELECT;
- `N` Symbol SELECTs (the only per-file projection consumed by `_load_facts`);
- `N` duplicate per-file Chunk SELECTs after all Chunks were already instantiated;
- `N` Relationship SELECTs and Relationship objects that Evidence planning never consumes.

An instrumented four-file index produced 13 SELECTs: 5 against `chunks`, 4 against `symbols`, and 4 against `relationships`, matching `1 + 3N`. Supplemental `search_repository` subsequently calls `store.get_chunks()` again (`retrieval/service.py:68-87`), so a successful collection currently performs a second global Chunk materialization as well.

No current test counts these reads. `test_map_outputs_and_repeated_evidence_remain_within_persisted_bounds` checks reference count, artifact bytes, and replay idempotence only (`tests/performance/test_knowledge_map_budget.py:37-72`).

### Existing APIs and the smallest scope-directed read shape

Existing APIs do not expose complete Chunks by path or ID:

- `page_files` pages file metadata only (`store.py:615-649`);
- `page_chunk_ids` pages `(ordinal, id)` only and cannot produce mandatory source text (`store.py:651-667`);
- `get_symbols_by_id` retrieves a caller-supplied Symbol set in one query (`store.py:466-477`);
- `get_parse_result(path)` is the only path-directed complete-Chunk read, but necessarily loads Symbols and Relationships too;
- `get_chunks()` loads every Chunk.

The exact planner only needs Chunks from paths reachable from required anchors, then Symbol metadata for the non-null `symbol_id` values on those Chunks:

| Anchor kind | Paths needed by the current fallback contract |
|---|---|
| symbol | The symbol fact's owning file path; a missing definition falls back to that file. |
| file | That file path. |
| module | Child file paths in POSIX order until a representative exists; loading all child paths preserves the current deterministic minimum. |
| generated current scopes | Cluster anchors are files; flow anchors are symbols; node-tour anchors are symbols/modules; cluster/flow tours reuse those anchors (`flows.py:326-419`). |

The smallest typed Store boundary not already present is therefore a stable complete-Chunk lookup for a bounded batch of file paths (equivalent SQL projection to `get_chunks`, with `WHERE file_path IN (...) ORDER BY file_path, ordinal`). The caller can use fixed-size path batches, deduplicate returned `symbol_id` values, and use the existing `get_symbols_by_id` in matching fixed-size batches. The repository already uses page size 256 for deterministic index inventory reads (`knowledge_map/snapshot.py:23,71-130`); no general Store batch-size constant currently exists.

This shape preserves the representative tie rules because every Chunk on every anchor-reachable path and every corresponding Symbol remains available. It also preserves mandatory preflight-before-search: scope-directed direct Chunks are loaded and packed first; only a successful preflight reaches the existing supplemental search. The latter still performs its existing global retrieval read, but the planner no longer adds an earlier global Chunk scan or constructs unrelated ParseResults.

Freshness validation has a related global read: `_validate_references` builds a dictionary from every Chunk for a snapshot whose reference count is already capacity-bounded (`evidence_service.py:392-417`). The Store has no Chunk-by-ID equivalent of `get_symbols_by_id`; whether that adjacent read is included in this task affects the API surface but not either reported defect.

### Defect 2: missing required-anchor Chunks are reachable

The planner raises this exact error when `_representative_chunk` returns `None`:

```python
RepositoryError(
    "knowledge_map_evidence_capacity_exceeded",
    "A required Knowledge Map anchor has no complete indexed Chunk.",
    details={
        "provided": 0,
        "required": 1,
        "recovery_action": "reset_scope_or_raise_capacity",
        "retry_mode": "after_recovery",
    },
)
```

(`knowledge_map/evidence.py:78-97`.) Neither resetting the scope nor raising `evidence_references_per_snapshot` can create a Chunk, so the advertised recovery action cannot resolve this condition.

The condition occurs through supported indexing behavior, not only a synthetic artifact. A real repository containing one empty `empty.py` produced a Map with one cluster scope and one tour scope, both anchored to the empty file. `map evidence` then returned `knowledge_map_evidence_capacity_exceeded` with `provided=0`, `required=1`, and `reset_scope_or_raise_capacity`. The path is:

1. empty/whitespace source legitimately produces no Chunks (`tests/unit/parsing/test_text.py:61`);
2. every Manifest file becomes a file fact (`lifting.py:50-82`);
3. every file fact is grouped into a cluster (`topology.py:37-39,71-95`);
4. cluster members become required anchors and cluster tours copy those anchors (`flows.py:343-419`);
5. file fallback returns `None` when the file has no candidate Chunks (`evidence.py:154-166`).

Skipped files can follow the same structural route because lifting consumes `snapshot.files` without filtering `ReadStatus` (`lifting.py:50-82`), while skipped parse results have no parsing objects.

### Compatibility analysis of the three behavior families

| Behavior family | Existing-contract fit | Compatibility impact |
|---|---|---|
| Filter unavailable semantic scopes during generation | Requires more than dropping a `ScopeContract`: Schema 1.0 requires contracts to cover every cluster, flow, and tour exactly (`models.py:1778-1811`). The corresponding cluster/flow/tour structures (and dependent tour adjacency/counts) must also be filtered, or the artifact becomes invalid. | Changes deterministic Map content, revisions, architecture/tour visibility, coverage counts, and existing exact scope tests. It prevents publishing a scope that cannot satisfy mandatory Evidence, but makes empty/skipped-file structures absent from those views. This is a user-visible product-semantics choice. |
| Add a dedicated unavailable-anchor error | Accurately separates source availability from token/reference capacity while preserving all deterministic structures and scope IDs. | Additive public machine-contract change: stable code, recovery action, error matrix/applicability, CLI docs in both locales, process tests, and spec must be extended. The scope remains visible but cannot be enriched until source/index/map state changes. |
| Reuse an existing error | `knowledge_map_evidence_not_found` is the nearest existing phrase, but today it applies only to `enrich` when a scope has no snapshot and prescribes `collect_evidence`; using it for `evidence` changes its applicability and requires a different actionable recovery. `knowledge_map_scope_not_found`, `knowledge_map_evidence_stale`, budget, and capacity codes describe different states. | Avoids a new code string but still changes the frozen command/error matrix and either overloads an existing recovery action or changes that public action. No existing error/recovery pair exactly describes “current scope exists but indexed source has no complete Chunk.” |

The current scope/anchor rules do not support silently dropping one required anchor: cluster Evidence requires one representative for every direct member file, exact anchor arrays are schema-validated, and mandatory direct Evidence is the grounding boundary (`knowledge-map-contracts.md:227-234`; archived design `08-30-map-evidence-enrichment/design.md:29-41`). Using an unrelated global fallback Chunk would likewise cease to represent the required fact.

### Smallest contract-preserving design shape identified

For the read-amplification defect, the narrow shape is: resolve the persisted scope contract before fact loading; expand only its required-anchor paths; load complete Chunks in bounded path batches; load only referenced Symbols through bounded `get_symbols_by_id` batches; run the unchanged pure planner and mandatory preflight; then invoke supplemental retrieval. This preserves query-plan identity, tie ordering, direct-before-supplemental order, error precedence after scope validation, and persisted Evidence shape.

For missing anchors, no option is contract-neutral. Preserving deterministic Map structures requires an explicit unavailable-source error behavior; filtering requires changing deterministic scope/view semantics. Selecting between those is user-owned product policy, not an indexing implementation detail.

### Tests implied by the existing contracts

1. **Store unit boundary**: complete Chunks for a bounded path batch, stable `(file_path, ordinal)` order, no off-scope paths, empty input, invalid batch bounds, and multi-batch equivalence.
2. **Planner unit**: preserve current cluster/flow/tour ordering, definition/file/module fallback, deduplication, anchor accumulation, and query-plan hash when facts arrive through scoped batches; add an explicit no-Chunk anchor fixture for the selected public behavior.
3. **Read-count performance test**: an `N`-file repository with a one-file scope should prove mandatory planning does not call `get_parse_result`, does not read Relationships, and its direct-fact SQL/object reads scale with anchor-reachable path batches rather than Manifest file count. Account separately for the existing global read inside supplemental `search_repository`.
4. **Preflight integration**: preserve the existing assertion that supplemental search does not run when mandatory capacity/token/source availability fails, and preserve artifact bytes.
5. **Real availability integration**: empty and skipped files should build successfully and then assert the chosen scope/error behavior, exit `3`, safe bounded details, actionable recovery, and no write.
6. **Public error matrix/process tests**: any new code or changed applicability must update `SHARED_ERROR_ROWS`, `ERROR_COMMANDS`, independently frozen expected cells, generated real failure cases, and paired EN/zh-CN CLI documentation (`tests/integration/test_map_errors.py`).
7. **Deterministic compatibility tests if filtering is selected**: exact cluster/flow/tour/scope coverage, tour adjacency, coverage included/omitted accounting, deterministic revision, rebuild preservation/reset behavior, and views for repositories mixing chunk-bearing and no-Chunk files.

### Related Specs

- `.trellis/spec/backend/knowledge-map-contracts.md:176-326` — mandatory complete Evidence, preflight ordering, capacity classification, and required tests.
- `.trellis/spec/backend/knowledge-map-contracts.md:328-443` — public command/error and recovery contract.
- `.trellis/spec/backend/database-guidelines.md:7-108` — typed stable bounded SQLite query conventions and schema compatibility rules.
- `.trellis/tasks/archive/2026-08/08-30-map-evidence-enrichment/design.md:29-47` — original exact representative and capacity design.
- `.trellis/tasks/archive/2026-08/08-30-knowledge-map-refactor/design.md:371-427` — frozen Version 1 public error/recovery matrix.

## User-Owned Product Decision

Should empty/skipped-file architecture remain visible as cluster/tour scopes and fail Evidence collection with an explicit “indexed Evidence unavailable” recovery, or should structures that cannot satisfy mandatory Evidence be omitted from the deterministic Map and its views? The former preserves current deterministic visibility but expands the public error contract; the latter changes deterministic Map/view semantics and coverage.

## Caveats / Not Found

- No existing Store API returns complete Chunks for a bounded path or ID set; `page_chunk_ids` is insufficient for packing Evidence text.
- No existing error/recovery pair precisely models a valid current scope whose required source has zero complete Chunks.
- Existing performance tests do not instrument SQLite reads or object materialization.
- Trellis reported no globally active task, but the injected task explicitly identified `.trellis/tasks/08-31-map-evidence-planning-corrections`; this report was persisted only under that requested child task.
