# Research: Persistence contracts and CLI boundaries

- **Query**: Inspect persistence contracts and CLI boundaries relevant to a deterministic knowledge map and identify compatibility constraints.
- **Scope**: internal
- **Date**: 2026-08-30

## Update: Active Trellis Specs

Update: active Trellis backend specs were added after this research snapshot.
The current active specs listed below supersede the earlier “not found” observation.

- `.trellis/spec/backend/index.md` identifies the active backend contracts.
- `.trellis/spec/backend/repository-classification.md` governs strict current-index snapshot identity and bounded deterministic manifest signals.
- `.trellis/spec/backend/wiki-template-contracts.md` confirms Wiki templates/state remain independently owned and unchanged by Knowledge Map Version 1.
- `.trellis/spec/backend/tooling-integration-contracts.md` requires complete repository-owned references, exact staged allowlists, and clean-snapshot Make/Ruff verification.

Historical “no `.trellis/spec/**/*.md`” lines below are retained as snapshot history only.

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/repo_dive/indexing/manifest.py` | Strict public manifest Schema 2.0 and deterministic build parameters/counts. |
| `src/repo_dive/indexing/service.py` | Generation-based index build, validation, current pointer, and atomic publication. |
| `src/repo_dive/indexing/store.py` | Strict SQLite Schema 4 compatibility and read-only consumer boundary. |
| `src/repo_dive/indexing/schema.sql` | Physical database contract. |
| `src/repo_dive/schema.py` | Stable command result/error envelope Schema 1.0 and canonical JSON serialization. |
| `src/repo_dive/cli.py` | Root process I/O, dispatch, JSON stdout, stderr diagnostics, and exit-code handling. |
| `src/repo_dive/commands/index.py` | Public index arguments and result contract. |
| `src/repo_dive/wiki/store.py` | Strict Wiki JSON reads and atomic artifact replacement. |
| `src/repo_dive/storage/atomic.py` | Repository-confined atomic write primitive. |
| `tests/integration/test_index_command.py` | Public index schema/count/idempotence assertions. |
| `tests/integration/test_cli_io.py` | Machine-parseable JSON and ANSI-free process output assertions. |
| `tests/integration/test_recovery.py` | Persisted-state failure/recovery behavior. |

### Code Patterns

#### Three independent schema identities

The code currently exposes distinct compatibility versions:

1. Command envelope Schema `1.0` (`src/repo_dive/schema.py:9,35-73`).
2. Index manifest Schema `2.0` (`src/repo_dive/indexing/manifest.py:16,117-186`).
3. SQLite index Schema `4` (`src/repo_dive/indexing/store.py:30`; `src/repo_dive/indexing/schema.sql:93`).

Wiki state and Wiki metadata each use Schema `2.0` (`src/repo_dive/wiki/models.py:21-22`). These version numbers are not interchangeable.

`BuildParameters` records every setting currently considered capable of changing deterministic index output: include/exclude patterns, file/chunk limits, parser/tokenizer versions, SQLite schema version, and BM25 parameters (`src/repo_dive/indexing/manifest.py:23-58`). The manifest also binds build ID, repository fingerprint, sorted files and chunk membership, counts, optional embedding identity, source-control identity, and effective default exclusions (`src/repo_dive/indexing/manifest.py:61-186`).

Manifest reading strictly validates supported version and typed fields (`src/repo_dive/indexing/manifest.py:203-227,241-304`). SQLite open rejects any version other than exactly `INDEX_SCHEMA_VERSION` (`src/repo_dive/indexing/store.py:619-626`).

#### Generation publication

`IndexService.build` scans and identifies the repository, reuses an unchanged compatible generation, otherwise builds into a temporary directory, writes/reads the manifest, verifies source identity, and publishes only after validation (`src/repo_dive/indexing/service.py:106-231`). It validates foreign keys and SQLite integrity before constructing the manifest (`src/repo_dive/indexing/service.py:265-378`).

The stable `.repo-dive/index` path is a symlink/junction to exactly one child of `.repo-dive/index-generations`; consumers reject ordinary paths, broken pointers, or pointers escaping the generation directory (`src/repo_dive/indexing/service.py:560-609`). Publication moves the complete staging generation and atomically replaces the pointer, with Windows rollback handling (`src/repo_dive/indexing/service.py:637-702`).

Current public index output exposes `build_id`, fingerprint, file/chunk/symbol/relationship counts, SQLite schema version, and manifest schema version (`src/repo_dive/commands/index.py:127-152`). Tests pin SQLite `4`, manifest `2.0`, unchanged build-ID reuse, and rebuilt/reused counts (`tests/integration/test_index_command.py:24-53`).

#### CLI boundary

The root CLI imports command objects and only handles parser construction, process I/O, stable result/error envelopes, and exit translation (`src/repo_dive/cli.py:10-36,39-63,101-168`). JSON success writes one canonical, newline-terminated document to stdout (`src/repo_dive/cli.py:101-115`); JSON errors write an error envelope to stdout and a safe message to stderr (`src/repo_dive/cli.py:117-128`). The generic unexpected-error path emits `internal_operation_failed`, not exception details (`src/repo_dive/cli.py:154-163`).

Command modules configure arguments, call services, and map domain results to JSON/Markdown; for example `commands/index.py:28-105`. This matches the repository-wide source boundary in `AGENTS.md`.

#### Repository-owned artifact boundary

Index generation files live under `.repo-dive/index-generations/<build-id>/`; the stable pointer is `.repo-dive/index/` (`src/repo_dive/indexing/service.py:49-53`). Public Wiki state is exactly `.repo-dive/wiki.json`, `.repo-dive/metadata.json`, and `.repo-dive/wiki.md` (`src/repo_dive/wiki/store.py:23-25`). Wiki JSON writes replace complete documents atomically; Markdown skips a write when bytes are unchanged (`src/repo_dive/wiki/store.py:68-96`).

No persisted knowledge-map, graph-view, enrichment, architecture-view, flow-view, or reading-path artifact path currently exists.

### Compatibility Constraints

| Constraint | Anchor | Consequence for the task boundary |
|---|---|---|
| Stable IDs are content/location derived, while index `build_id` is a new UUID for each rebuilt generation. | `src/repo_dive/parsing/models.py:77-134`; `src/repo_dive/indexing/service.py:334-378` | Derived data must distinguish stable fact identity from generation identity. |
| Incremental reuse requires exact `BuildParameters` equality. | `src/repo_dive/indexing/service.py:147-166,248-270` | Any index-output-affecting parser/schema parameter belongs in compatibility identity. |
| Published consumers use a validated read-only generation. | `src/repo_dive/indexing/service.py:560-609`; `src/repo_dive/indexing/store.py:99-115` | Read views should not mutate SQLite during query operations. |
| SQLite schema compatibility is exact, with no in-place migration path in `IndexStore.open`. | `src/repo_dive/indexing/store.py:619-626` | A physical table change is an index schema event and causes rebuild/open compatibility behavior. |
| Manifest parsing rejects unsupported versions and malformed typed content. | `src/repo_dive/indexing/manifest.py:203-227` | New public persisted fields require an explicit manifest contract decision rather than permissive loading. |
| CLI JSON has exactly one envelope document and no ANSI. | `src/repo_dive/schema.py:76-86`; `tests/integration/test_cli_io.py:6-26` | A map command/view must fit the common command envelope and keep diagnostics on stderr. |
| Large operations require explicit budgets and search results max at 50. | `src/repo_dive/retrieval/service.py:21-24,51-67`; `AGENTS.md` CLI contract | Graph output cannot be implicitly unbounded. |
| Domain modules do not depend on terminal rendering/provider/environment lookup. | `docs/en/architecture.md:65`; `AGENTS.md` source boundaries | Derivation and rendering remain separate boundaries. |

### Claim Verification

- **Persistence is already atomic and generation-based:** correct for the index, and atomic complete-document replacement exists for Wiki state.
- **The raw graph has a public standalone persistence contract:** incorrect. Graph tables are private parts of SQLite Schema 4; only aggregate relationship counts and index identity appear in the manifest/CLI result.
- **A knowledge-map CLI boundary exists:** not found. Root commands are `init`, `index`, `search`, `context`, and `wiki` (`src/repo_dive/cli.py:30-36`).
- **Existing graph data can be read without product-side effects:** correct through `load_published_index` plus `IndexStore.open_readonly` (`src/repo_dive/retrieval/service.py:65-69`).

### Likely Test Locations

- `tests/unit/indexing/test_store.py`: physical schema, strict versions, typed round trips, foreign keys, and read-only behavior.
- `tests/unit/indexing/test_manifest.py`: persisted public identity, strict decoding, and compatibility parameters.
- `tests/unit/indexing/test_service.py` and `tests/integration/test_recovery.py`: staging, publication failure, old-generation preservation, current-pointer validation, and rebuild behavior.
- `tests/integration/test_index_command.py`: observable schema versions/counts/idempotence if graph artifacts remain index-owned.
- `tests/integration/test_cli_io.py` and `tests/unit/test_cli.py`: envelope, stdout/stderr, invocation errors, and command registration for any public boundary.
- `tests/integration/test_security.py`: repository confinement and path traversal for any new artifact or input.
- `tests/performance/test_index_scaling.py`: asymptotic index/persistence behavior.

## External References

None. This request was an internal implementation audit.

## Related Specs

- No `.trellis/spec/**/*.md` files were found.
- `docs/decisions/001-atomic-index-generations.md` records the generation-publication decision.
- `docs/en/cli-contract.md:20-28,62-102` describes current commands and deterministic/model boundaries.
- `docs/en/architecture.md:137-154` describes index storage and recovery.

## Caveats / Not Found

- `docs/en/architecture.md:145` says Wiki state uses Schema `1.0`, while current code and `docs/en/wiki-workflow.md:61-66` use strict Schema `2.0`; code/tests are the implementation authority.
- Index manifest `build_id` uses UUID generation (`src/repo_dive/indexing/service.py:346`), so complete command bytes are not deterministic across a forced rebuild even when derived fact ordering is deterministic. An unchanged index is reused with the same build ID.
- No migration framework is present for SQLite Schema 4; `allow_schema_upgrade=True` lets the build service observe an old manifest and rebuild, while ordinary consumers require the current schema (`src/repo_dive/indexing/service.py:147,592-609`).
