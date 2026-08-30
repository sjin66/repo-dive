# Implementation Plan

## Preconditions

- Keep this task in `planning` until the user approves the final planning summary.
- Execute against the governed Wiki Schema `2.0` integration work. If that activation
  task is not yet implemented, merge this plan into its activation sequence rather than
  creating a separate persisted Schema `1.x`.
- Before editing, load `trellis-before-dev`, the task context manifests, PRD, design,
  and the current template/Markdown validation contracts.
- Preserve unrelated dirty worktree changes and the last valid `.repo-dive/wiki.md`.

## Ordered TDD Steps

1. **Lock the cross-layer contracts with failing tests.**
   - Add model/serialization tests for ordered Subsections, stable identities, direct
     source validation, contract hashing, and Schema `2.0` strict decoding.
   - Add template parity tests proving every registered Page resolves an intentional
     Subsection outline in `en`, `zh-CN`, and `ja`.
   - Add legacy tests proving Schema `1.0` bytes and prior Markdown remain untouched.

2. **Implement governed Subsection models and composition.**
   - Extend language-neutral template nodes/resources and normalized Page contracts.
   - Persist exact Subsection contracts and expose them through init/evidence/status.
   - Update Page structural equality/invalidation to include ordered outline fields.
   - Checkpoint: model, composition, and state round-trip unit tests pass.

3. **Enforce heading hierarchy at page submission.**
   - Add Schema `2.0` submission cases for one exact ordered body/citation record per
     Subsection and all-or-nothing Page persistence.
   - Add AST cases for optional H5/H6 detail and rejection of H1-H4 in each fragment.
   - Implement bounded Page/Subsection/line diagnostics and no-write failure behavior.
   - Require each non-documentation-only Subsection to cite direct Evidence that covers
     its contract; keep Page as the only lifecycle and retry unit.
   - Checkpoint: page validator and submission integration tests pass.

4. **Add mandatory direct Evidence reservation.**
   - Add failing retrieval/service tests where relevant paths are absent from normal
     top-N candidates, share a Chunk, exceed per-file diversity, or cannot fit budget.
   - Implement bounded path-scoped selection, deterministic mandatory ordering,
     role/coverage projection, and pre-mutation budget failure.
   - Keep general `search`/`context` packing behavior unchanged.
   - Add an evaluation case showing improved implementation-source coverage for the
     retrieval/Context/security Wiki pages from the review.
   - Checkpoint: unit, Wiki Evidence integration, and evaluation tests pass.

5. **Capture index corpus and source identity.**
   - Add clean Git, dirty Git, untracked, unborn HEAD, non-Git, probe-failure, and
     deterministic-manifest tests.
   - Extend index manifest/build identity with source control, commit, dirty state, and
     effective default excluded directories; bump only the planned compatible manifest
     schema boundary.
   - Copy immutable source identity into governed Wiki metadata and status output.
   - Checkpoint: index freshness, manifest round-trip, and Wiki metadata tests pass.

6. **Localize and assemble the complete Wiki shell.**
   - Add exact golden outputs for all three locales, including scope/version labels,
     three-level contents, stable Subsection anchors, Related pages, and Sources.
   - Pass a typed build context into the pure assembler; insert anchors only at
     AST-validated H4 Subsection locations.
   - Add concurrent index/source identity change tests and verify failed build preserves
     previous Markdown.
   - Checkpoint: assembler, final AST validation, atomic build, and idempotence tests
     pass.

7. **Improve developer and terminology templates.**
   - Update software-oriented contracts and all `en`, `zh-CN`, and `ja` resources with
     developer setup, common operations, evidenced extension recipes, recovery, and
     glossary Subsections.
   - Update the Wiki Skill and workflow reference to require direct implementation
     paths and review direct/supplemental Evidence coverage before generation.
   - Verify package resource parity and no locale fallback.

8. **Update all public documentation and examples.**
   - Update executable help and JSON examples for Subsections, direct Evidence roles,
     source identity, and scope disclosure.
   - Update matched `docs/en/` and `docs/zh-CN/` pairs, AGENTS calling workflow if the
     public command sequence changes, package smoke, and evaluation contracts.
   - Remove examples that present H2 caller headings below H3 Pages or a clean commit for
     dirty indexed bytes.

9. **Run focused and full quality gates.**
   - Run focused Wiki/template/index/retrieval tests after each checkpoint.
   - Run `make check` and `make test-all` from the freshly prepared environment required
     by the repository.
   - Run package smoke and the relevant retrieval/Wiki evaluation suite.
   - Run `trellis-check` for spec compliance, cross-layer projection consistency,
     localization parity, security bounds, and backward-state preservation.

10. **Manual end-to-end acceptance.**
    - Generate a Chinese Wiki for this repository with explicit exclusions.
    - Confirm three-level contents, H1-H6 outline validity, Chinese framework labels,
      direct implementation citations, developer operations/glossary coverage, exact
      corpus disclosure, and commit/dirty/build/fingerprint information.
    - Run an unchanged second build and confirm identical SHA-256 and `changed: false`.
    - Do not treat the generated local `.repo-dive/` artifacts as source changes.

## Validation Commands

```bash
make setup
make check
make test-unit
make test-all
make package-smoke
```

Use existing focused pytest entry points for Wiki models/templates/assembler, Wiki
integration workflows, index manifest/service, security, recovery, and performance
before the full targets. Do not replace Make targets with duplicated tool invocations in
the completion report.

## Risky Boundaries

- Persisted Wiki/metadata and index manifest schema activation.
- Page invalidation when outline, locale, guidance, source paths, or index identity
  changes.
- Mandatory Evidence reservation under a single explicit token budget.
- AST line mapping when inserting stable Subsection anchors without rewriting prose.
- Locale catalog/resource parity across `en`, `zh-CN`, and `ja`.
- Build-time index race checks and preservation of the previous Markdown.
- Package inclusion of every updated template and Skill resource.

## Rollback Points

- Before public Schema `2.0` activation, revert internal adapters/tests as one unit with
  no persisted-state migration.
- After activation, never downgrade or rewrite persisted Schema `2.0`; preserve state and
  the last valid `wiki.md`, and fail with an unsupported-version diagnostic on an older
  binary.
- A failed Evidence or build step must leave the prior Page state/Markdown intact except
  for the established safe failed-state transition.

## Start Gate

Before `task.py start`, confirm:

- the user explicitly approved the latest planning summary;
- the governed Schema `2.0` sequencing/dependency is available;
- `implement.jsonl` and `check.jsonl` contain real context entries;
- no acceptance criterion conflicts with the active template-governance task;
- the current dirty worktree has been reviewed so unrelated changes are preserved.
