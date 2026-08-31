# Knowledge Map Final Integration Corrections

## Goal

Close the remaining parent P3/P4 release-proof gaps without changing the frozen
Knowledge Map product contract. The result must demonstrate each public failure through
its owning parser, adapter, domain, store, or filesystem path; prove enrichment writer
contention and bounded semantic growth; restore bilingual schema parity; and pass the
exact clean-snapshot release gates.

## Background

The independent parent review found three product-owned gaps:

- `tests/integration/test_map_errors.py:240-324` runs the real parser and command
  adapter, but most applicability cells synthesize the target error by replacing a
  public `KnowledgeMap*Service` method. This does not prove the owning validation,
  precedence, or store path required by the parent design.
- `tests/integration/test_map_concurrency.py:88-215` coordinates build/reset and
  build/Evidence, but no contested enrichment writer participates.
  `tests/performance/test_knowledge_map_budget.py:34-69` proves Evidence replay only,
  not bounded enrichment growth and capacity exhaustion.
- `docs/en/architecture.md:139` and `docs/zh-CN/architecture.md:139` report Index
  Manifest Schema `1.0`; `src/repo_dive/indexing/manifest.py:16` declares `2.0`.

The implementation already routes build, Evidence, enrichment, and reset through the
single `MapStore` transaction and already rejects strict wrong-scope claim references.
This child therefore adds missing executable evidence; it does not redesign those
contracts.

During approved implementation, the real `index_not_found` fixtures exposed one
runtime defect: `load_published_index` supplies an absolute index path and the Map root
adapter does not remove it. All six Map commands therefore disclose the selected host
repository path in JSON. The existing Map adapter already removes the same `path` field
for repository-selector errors, so the minimal correction belongs in that established
Map-only sanitization boundary and must leave non-Map error details unchanged.

### Resolved Planning Rollback: Unreachable Validate Row

Real owning-path implementation found that the parent row `map validate` ->
`knowledge_map_validation_failed` is not reachable through the current public runtime:

- `MapStore.read_artifact()` strictly decodes structural reference, ordering, revision,
  hash, and persisted Evidence invariants and maps every such failure to
  `knowledge_map_invalid`.
- `KnowledgeMapEnrichmentService.validate()` can additionally return
  `knowledge_map_stale` or `knowledge_map_evidence_stale`, but it does not create or
  commit a candidate artifact.
- `knowledge_map_validation_failed` is emitted only by
  `MapWriteTransaction.commit()` when a writer candidate is not the next revision,
  matching the backend executable contract.

Therefore FIC-R1 could not preserve this parent applicability cell and prove it through
an owning public path at the same time. The approved resolution corrects the parent
matrix: strict persisted structural/invariant failures remain
`knowledge_map_invalid`; stale persisted Evidence reached by `map validate` is
`knowledge_map_evidence_stale`; and `knowledge_map_validation_failed` remains a
writer-only candidate-revision error. No runtime validation behavior is added, and no
synthetic public-service exception injection may be used to paper over the original
contradiction.

## Requirements

### FIC-R1: Real Public Error Applicability Evidence

- Preserve the corrected parent error/applicability tables and the exact six-command
  public CLI.
- Every checked command/error cell must execute the real root parser, dispatch, command
  adapter, and public service method.
- Deterministically reproducible conditions must use real repository, index, artifact,
  Evidence, submission, budget, or path fixtures. Environmental and race failures may
  inject only at the narrow owning store, atomic-write, index-publication, filesystem,
  or domain-operation seam.
- Tests must not replace `MAP_COMMAND.handler` or a public `KnowledgeMap*Service`
  method solely to raise the expected row.
- Each cell must assert exact error code, exit code, one Schema 1.0 JSON document,
  command identity, closed retry/recovery values, safe stderr, no ANSI, and unchanged
  artifact bytes for writer failures. Combined-failure tests must pin normative
  precedence.
- The test table must fail if a parent applicability cell is omitted or an extra cell
  is silently introduced.

### FIC-R2: Enrichment Contention And Semantic Capacity Evidence

- Coordinate a real enrichment writer against a different public writer through the
  shared `MapStore.write_transaction` path without sleeps.
- Exactly one non-equivalent intent may win; the loser returns the stable revision
  conflict, and the persisted artifact must equal one complete valid winner state with
  a single revision increment and no lost semantics.
- Exercise accepted semantic growth up to persisted count/reference/input capacities,
  exact enrichment replay with byte stability, and the first over-capacity operation
  failing with the correct stable error while preserving prior bytes.
- Assert bounded counts and bytes rather than wall-clock latency.

### FIC-R3: Matched Documentation Parity

- Update both architecture documents to report Index Manifest Schema `2.0` while
  retaining SQLite Schema `5`, Wiki Schema `2.0`, and Knowledge Map Schema `1.0`.
- Add or update a repository contract assertion so these constants cannot drift again.
- Keep English and Chinese headings and technical contracts equivalent.

### FIC-R4: Exact Release Verification

- Run focused Map error, concurrency, budget, security, recovery, documentation, and
  compatibility tests before full repository checks.
- Run `make check`, `make test-unit`, `make test-all`, `git diff --check`, both
  no-gitignore Ruff commands, and root/Map/six-subcommand help smoke tests against the
  exact allowlisted clean snapshot on Python 3.11+ (prefer the repository's Python
  3.12 environment).
- Local ignored Host integrations and `.codegraph/` are not product inputs. They must
  remain untouched and excluded from the clean snapshot rather than reformatted.

### FIC-R5: Scope Discipline

- Do not change the frozen artifact, budget, error, recovery, permission, transaction,
  or public command contracts.
- Extend the existing Map-only error sanitization in `src/repo_dive/cli.py` so
  `index_not_found` cannot expose its absolute `details.path`. Preserve the underlying
  indexing error and every non-Map command's current details.
- Do not modify Wiki code, Host skills/hooks/configuration, `.codegraph/`, or any
  `docs/superpowers` file.
- Do not add a model call, dependency, writer, lock, alias, heuristic, or fixed latency
  assertion.
- No other `src/` change is allowed. Any additional runtime defect returns this child
  to planning before implementation continues.

## Acceptance Criteria

- [x] **FIC-AC1:** Every parent shared and command-specific applicability cell reaches
  its owning real path through the public process boundary, with complete envelope,
  precedence, safety, and no-write assertions; no public service or command handler is
  replaced merely to synthesize the row.
- [x] **FIC-AC1a:** Real `index_not_found` failures for all six Map commands contain no
  absolute repository/index path, while an equivalent non-Map error retains its
  existing details contract.
- [x] **FIC-AC2:** A coordinated enrichment-vs-other-writer test proves one complete
  winner, one stable conflict, one revision increment, and no lost update.
- [x] **FIC-AC3:** Semantic growth/replay/capacity tests prove persisted limits, stable
  no-growth replay, correct first-over-limit error, and byte preservation without time
  thresholds.
- [x] **FIC-AC4:** English and Chinese architecture docs agree with executable Index
  Manifest `2.0`, SQLite `5`, Wiki `2.0`, and Knowledge Map `1.0` constants, protected by
  a repository contract test.
- [x] **FIC-AC5:** Focused suites, `make check`, `make test-unit`, `make test-all`,
  `git diff --check`, clean-snapshot no-gitignore Ruff, and all Map help smoke tests pass
  on the exact allowlisted Python 3.11+ snapshot.
- [x] **FIC-AC6:** Independent review reports no unresolved correctness, concurrency,
  provenance, budget, security, compatibility, or documentation finding and confirms
  KM-AC4, KM-AC8, KM-AC9, KM-AC11, and KM-AC12 can return to PASS.
- [x] **FIC-AC7:** Git history and status confirm `.codegraph/`, Host integrations,
  Wiki code, `docs/superpowers`, and unrelated files were not modified or staged.

## Out Of Scope

- Product behavior or public schema changes other than enforcing the already-frozen
  Map diagnostic non-disclosure contract for `index_not_found`.
- New error rows, recovery actions, commands, aliases, capacities, or derivation rules.
- General performance benchmarking or fixed-duration requirements.
- Cleanup of ignored Host integrations or `.codegraph/`.
- Parent archival before a new independent P3/P4 review.

## Verification Evidence

- Focused changed suites: `162 passed` in the working tree after independent fixes.
- Independent exact clean Python 3.12 snapshot: `make check`, no-gitignore Ruff,
  `git diff --check`, and root/Map/six-subcommand help checks passed;
  `make test-unit` reported `465 passed`; `make test-all` reported `702 passed`.
- Independent review fixed complete-cell coverage, writer byte-preservation assertions,
  under-lock index-change precedence, and raw enrichment-input capacity proof, then
  reported no unresolved FIC-AC1 through FIC-AC7 finding.
- The local dirty-worktree unit run reported `464 passed, 1 failed` only because ignored
  Host Wiki skills duplicate the portable skill. Those local integrations were absent
  from the required clean snapshot and were not modified.
- Scope inspection found no tracked diff under `.codegraph/`, `src/repo_dive/wiki/`, or
  `docs/superpowers/`; `.codegraph/` remains an untouched untracked local directory.
