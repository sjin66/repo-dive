# Implementation Plan: Template-governed multilingual Wiki generation

## Delivery Order

The parent task owns requirements, shared contracts, and final integration review. It
does not directly own product-code changes. Child tasks execute in the following
dependency order.

## 1. Deterministic Repository Classification

Task: `08-29-repository-classification`

- Define classifier/taxonomy models and strict JSON projections.
- Add a bounded, versioned rule registry and manifest/path/language matchers.
- Implement threshold, margin, fallback, topology, facet, and override semantics.
- Add representative fixtures for every primary archetype, topology, facets, ties,
  weak evidence, malformed manifests, stable ordering, and secrecy.
- Expose a domain service ready for CLI adaptation; do not couple it to rendering.

Verification: focused unit/integration tests, `make check`, and `make test-all`.

## 2. Composed Multilingual Templates

Task: `08-29-multilingual-wiki-templates`

Dependency: classifier taxonomy IDs from Task 1.

- Define immutable contribution/contract/node/slot models and deterministic hashes.
- Implement base + topology + facet composition and reject registry conflicts.
- Author detailed Markdown resources for every primary type and supported overlay in
  `en`, `zh-CN`, and `ja`, including instructional comments.
- Add locale catalogs for framework labels and exact parity checks.
- Add resource compilation, contract/guidance hashing, and package-data discovery.
- Test every registered combination class, locale parity, strict closed structure,
  extension slots, and deterministic serialization.

Verification: resource registry tests, locale parity tests, package-source tests,
`make check`, and `make test-all`.

## 3. Markdown AST Conformance Validation

Task: `08-29-markdown-ast-validation`

Dependency: node contracts and extension-slot model from Task 2.

- Add `markdown-it-py>=4.2,<4.3` as a core dependency and persist the exact runtime
  parser package/version in governance identity.
- Implement `repo-dive-gfm-subset-1` with CommonMark + table and inert HTML tokens.
- Normalize parser tokens into a narrow internal tree consumed by validation rules.
- Implement page-body, state, and full-document validation using one pure engine.
- Implement bounded deterministic diagnostics without source/body disclosure.
- Add adversarial fixtures for hierarchy escapes, duplicates, ordering, wrong node
  types, comments/placeholders, content bounds, links, code fences, tables, extension
  slots, CRLF locations, nesting, and diagnostic truncation.

Verification: parser-profile and validator tests, dependency/package smoke,
`make check`, and `make test-all`.

## 4. Governed Wiki State Lifecycle

Task: `08-29-governed-wiki-state`

Dependencies: Tasks 1-3.

- Define strict Wiki/metadata Schema `2.0` and governance/page-contract identities.
- Persist complete normalized composed/page contracts rather than relying on hashes or
  old bundled registries.
- Implement `wiki init` domain behavior and exact idempotency.
- Integrate page-body validation before generated-state persistence.
- Implement identity-based invalidation and preserve unaffected pages/Evidence.
- Detect Schema `1.0` as `wiki_template_state_missing` without writes.
- Revalidate complete state and final assembled Markdown before atomic publication.
- Localize assembler-owned framework labels and preserve source-link contracts.
- Test crash/error preservation, stale Evidence, locale/template/parser changes,
  no-op behavior, concurrent submissions under an exclusive Wiki lock, and old
  `wiki.md` retention.
- Keep Schema `2.0` services behind typed internal entry points; do not switch existing
  public Schema `1.0` command dispatch in this child.

Verification: Wiki model/store/service/assembler tests, recovery integration tests,
`make check`, and `make test-all`.

## 5. CLI, Packaging, Documentation, And End-To-End Integration

Task: `08-29-wiki-template-cli-integration`

Dependencies: Tasks 1-4.

- Add `wiki classify`, `wiki init`, and `wiki validate` argument/JSON/Markdown adapters.
- Atomically activate Schema `2.0` for existing evidence/page/build/status commands;
  no intermediate public workflow may require governed state without `wiki init`.
- Return validation nonconformance through the existing exit-`2` error envelope with
  safe bounded diagnostic details.
- Extend evidence/status/build output with bounded governance identity and page contract.
- Add explicit generation-budget accounting for complete guidance plus Evidence.
- Keep `wiki structure` as a documented one-release deprecated compatibility path.
- Add end-to-end tests for all commands, exit codes, JSON isolation, stdin/file bounds,
  exact diagnostics, non-mutation, regeneration, and final-template conformance.
- Include every template/locale resource in wheel and sdist smoke tests.
- Update executable help, AGENTS workflow, README where applicable, and matched
  `docs/en/` + `docs/zh-CN/` CLI/Wiki/development/architecture documentation.
- Add evaluation cases demonstrating classification and conformance improvements.

Verification: focused CLI/integration/contract/package tests, then fresh-environment
`make setup`, `make check`, and `make test-all`.

## Checkpoints

- After Tasks 1-2: review taxonomy coverage, all three locale resources, contract
  composition, and package discovery before validator implementation.
- After Task 3: adversarial review of parser profile, diagnostic safety, and exact
  contract matching before state migration work.
- After Task 4: recovery and compatibility review before exposing public commands.
- After Task 5: full parent acceptance review across every PRD criterion.

## Risky Files And Rollback Points

- `src/repo_dive/wiki/models.py` and `store.py`: persisted Schema transition; preserve
  fixture bytes and reject unsupported/legacy state without repair.
- `src/repo_dive/wiki/service.py`: lifecycle/invalidation coupling; land only with
  recovery and idempotency coverage.
- `src/repo_dive/wiki/assembler.py`: exact public Markdown changes; gate localization
  to governed Schema `2.0` and maintain source anchors.
- `src/repo_dive/commands/__init__.py` and `cli.py`: process exit semantics; default
  error-envelope behavior must remain unchanged for all commands.
- `pyproject.toml` and package resources: verify both wheel and sdist before completion.

No child may rewrite existing Schema `1.0` artifacts in place or replace `wiki.md`
before a complete validated build. If a checkpoint fails, keep completed earlier
children and revise the next child's planning artifact rather than weakening the
shared contract.

## Final Review Gate

- Every parent acceptance criterion maps to at least one executable test.
- All primary/topology/facet registry entries have `en`, `zh-CN`, and `ja` guidance.
- Every conformance rejection is deterministic, bounded, safe, and non-mutating.
- CLI JSON mode emits exactly one document and returns the specified exit code.
- Documentation contracts and executable help agree.
- `make check` and `make test-all` pass from a fresh setup.
