# Relationship Provenance Index Schema Implementation Plan

## Dependency

None. This is the first implementation child and an independently rollbackable prerequisite.

## Task A1: Define Occurrence Relationship Contract

**Responsibility:** Pin immutable fields, validation, discriminator, deterministic ID, and serialization.

**Acceptance criteria:** RP-AC1 model cases pass; invalid ranges/path/confidence/discriminators fail; identical bytes yield identical IDs.

**Primary files:**

- `src/repo_dive/parsing/models.py`
- `tests/unit/parsing/test_models.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/parsing/test_models.py -q`

## Task A2: Capture Python Relationship Occurrences

**Responsibility:** Emit exact independent occurrences for Python containment/import/call/inheritance.

**Acceptance criteria:** repeated same-line calls and multi-alias imports remain separate; exact ranges and order are stable.

**Dependencies:** A1.

**Primary files:**

- `src/repo_dive/parsing/python_ast.py`
- `tests/unit/parsing/test_python_ast.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/parsing/test_python_ast.py -q`

## Task A3: Capture Tree-Sitter Occurrences And Normalize

**Responsibility:** Add exact Tree-sitter containment occurrence data and ID-only pipeline deduplication/order.

**Acceptance criteria:** declaration ranges are exact; endpoint-equivalent IDs survive normalization; duplicate identical IDs collapse deterministically.

**Dependencies:** A1.

**Primary files:**

- `src/repo_dive/parsing/tree_sitter.py`
- `src/repo_dive/parsing/pipeline.py`
- `tests/unit/parsing/test_tree_sitter.py`
- `tests/unit/parsing/test_pipeline.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/parsing/test_tree_sitter.py tests/unit/parsing/test_pipeline.py -q`

### Checkpoint A

- [ ] `.venv/bin/python -m pytest tests/unit/parsing -q`
- [ ] Repeat-parse occurrence snapshots are identical.
- [ ] Review proves no inferred locator is labeled exact.

Rollback: revert A1-A3 together before persistence changes.

## Task A4: Persist Schema 5 Occurrences

**Responsibility:** Change the relationship table/round-trip and validate owner path/integrity.

**Acceptance criteria:** RP-AC3 passes; repeated occurrences persist; read-only and integrity behavior remain intact.

**Dependencies:** A2, A3.

**Primary files:**

- `src/repo_dive/indexing/schema.sql`
- `src/repo_dive/indexing/store.py`
- `tests/unit/indexing/test_store.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/indexing/test_store.py -q`

## Task A5: Preserve Unique Graph And Retrieval Semantics

**Responsibility:** Group occurrences into stable adjacency and pin structural retrieval compatibility.

**Acceptance criteria:** RP-AC4/RP-AC5 pass; traversal budgets count unique adjacency; current scores/order/explanations are unchanged.

**Dependencies:** A4.

**Primary files:**

- `src/repo_dive/indexing/graph.py`
- `src/repo_dive/retrieval/structural.py`
- `tests/unit/indexing/test_graph.py`
- `tests/unit/retrieval/test_structural.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/indexing/test_graph.py tests/unit/retrieval/test_structural.py -q`

## Task A6: Bump Compatibility And Verify Rebuild

**Responsibility:** Increment parser/schema build identity and test reject/rebuild/recovery behavior.

**Acceptance criteria:** RP-AC6 passes; manifests expose current versions; failed rebuild preserves last generation.

**Dependencies:** A5.

**Primary files:**

- `src/repo_dive/indexing/manifest.py`
- `tests/unit/indexing/test_manifest.py`
- `tests/integration/test_index_command.py`
- `tests/integration/test_recovery.py`

**Verification:** `.venv/bin/python -m pytest tests/unit/indexing/test_manifest.py tests/integration/test_index_command.py tests/integration/test_recovery.py -q`

### Checkpoint B

- [ ] `.venv/bin/python -m pytest tests/unit/indexing/test_store.py tests/unit/indexing/test_graph.py tests/unit/retrieval/test_structural.py -q`
- [ ] `.venv/bin/python -m pytest tests/integration/test_index_command.py tests/integration/test_recovery.py -q`
- [ ] `make check`

Rollback: revert Schema/parser/manifest versions and all occurrence persistence as one unit. Do not retain a model the active SQLite schema cannot store.

## Completion Gate

- [ ] RP-AC1 through RP-AC7 pass.
- [ ] Existing search/context behavior remains green in focused regression tests.
- [ ] No Knowledge Map product file or public command was added.
