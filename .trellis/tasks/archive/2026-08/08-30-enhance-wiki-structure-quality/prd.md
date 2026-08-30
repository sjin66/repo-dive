# Enhance Wiki structure and quality

## Goal

Make generated Wikis detailed enough for developer use while preserving a deterministic,
evidence-grounded CLI boundary. A generated Wiki must expose a real three-level content
outline, maintain valid Markdown heading hierarchy, cite direct implementation Evidence,
and disclose the locale, corpus scope, and source version that bound its claims.

## Background

- The current public structure is only `Section -> Page`; `StructurePage` has no
  page-internal outline (`src/repo_dive/wiki/service.py:42-61`).
- The assembler owns H2 Section and H3 Page headings, but inserts the caller body
  unchanged (`src/repo_dive/wiki/assembler.py:42-53`,
  `src/repo_dive/wiki/assembler.py:66-88`). The reviewed Chinese Wiki therefore has H2
  body headings below H3 pages (`.repo-dive/wiki.md:25-33`).
- `relevant_files` currently contribute only `path:` query text
  (`src/repo_dive/wiki/service.py:679-696`); retrieval and budget packing do not
  guarantee that a named implementation file appears in the returned Evidence.
- The assembler hard-codes `Contents`, `Related pages`, and `Sources` in English
  (`src/repo_dive/wiki/assembler.py:25-31`, `src/repo_dive/wiki/assembler.py:77-86`),
  although Wiki metadata persists `output_language`.
- The published index manifest already records scan mode, include/exclude patterns,
  file counts, and build identity (`src/repo_dive/indexing/manifest.py:23-58`,
  `src/repo_dive/indexing/manifest.py:117-157`), but the final Wiki does not disclose
  them.
- Wiki metadata already has `source_commit`, but new state always writes `null`
  (`src/repo_dive/wiki/models.py:290-335`, `src/repo_dive/wiki/service.py:645-660`).
- The template registry already models H3 pages and H4/H5 body headings and provides
  exact `en`, `zh-CN`, and `ja` locale catalogs
  (`src/repo_dive/wiki/templates/registry.py:28-43`). This task extends that governed
  Schema `2.0` path rather than creating a second Schema `1.0` evolution.

## Requirements

### R1. Three-level Wiki structure

- The governed structure must represent ordered `Section -> Page -> Subsection` nodes.
- Every generated Page must have at least one Subsection. Each Subsection has a stable
  locale-neutral ID, localized title, focused description, and ordered direct source
  paths.
- Subsection IDs must be unique within their Page; the `(page_id, subsection_id)` pair
  is the stable global identity used for anchors and validation.
- `wiki init`, persisted Wiki state, `wiki evidence`, `wiki status`, and final assembly
  must preserve the exact Subsection order and identity.
- The final contents list must include Sections, Pages, and Subsections with stable
  links.

### R2. Correct heading ownership and hierarchy

- The CLI owns H1 Wiki, H2 Section, H3 Page, and H4 Subsection headings.
- Caller-generated content is scoped below one Subsection and may use only H5/H6
  headings. It must not repeat or override CLI-owned headings.
- Schema `2.0` Page submission must contain one ordered content fragment for each exact
  Subsection ID; the CLI emits the corresponding localized H4 heading during assembly.
- Page submission validation must reject, rather than silently rewrite, H1-H4 caller
  headings and must return bounded diagnostics identifying the Page/Subsection and
  one-based source line.
- `Related pages` and `Sources` remain CLI-owned H4 siblings after the Page's ordered
  Subsections.

### R3. Direct implementation Evidence

- Every Subsection declares at least one indexed direct source path unless its contract
  explicitly classifies it as documentation-only.
- `wiki evidence` must reserve and return at least one complete, query-relevant Chunk
  from each declared direct source path before filling the remaining budget with fused
  lexical/structural/optional-vector candidates.
- Direct Evidence must remain normal Evidence: repository-relative POSIX path, one-based
  inclusive lines, Chunk/content identity, stable Evidence ID, and freshness checks.
- Evidence output must distinguish required direct items from ranked supplemental items
  without weakening existing score/reason metadata.
- Each submitted Subsection must cite at least one direct Evidence item that satisfies
  that Subsection's contract; supplemental citations remain optional.
- If the complete required direct set cannot fit the explicit Evidence budget, the
  command must fail with a stable validation error before mutating Page state; it must
  not silently omit a required source or truncate a Chunk.

### R4. Localized framework labels

- `Contents`, `Related pages`, `Sources`, and the new scope/version disclosure labels
  must resolve from the exact persisted locale catalog.
- Runtime locales remain exactly `en`, `zh-CN`, and `ja`, with no normalization or
  fallback. English/Chinese developer docs remain a matched pair; no Japanese developer
  documentation tree is required.

### R5. Index scope disclosure

- The final Wiki must include a CLI-owned localized scope disclosure derived from the
  exact published index used for the build.
- It must report scan mode, explicit include/exclude patterns, effective default
  excluded directories, indexed/skipped file counts, index build ID, and repository
  fingerprint.
- Git mode must be described accurately as tracked plus unignored untracked files after
  the recorded filters. The disclosure must not claim to enumerate every Git ignore
  rule or every omitted file.
- Build must reject an index identity change between disclosure construction,
  validation, and atomic publication.

### R6. Developer operations guidance

- Software-oriented built-in templates must provide developer-facing coverage for
  installation/first run, common commands, local setup and verification, supported
  extension workflows, and common failure recovery.
- CLI/developer-tool templates must explicitly cover adding a parser, retriever, or
  Provider only when the repository exposes that extension boundary in direct Evidence.
- The Wiki generation Skill must request these topics when applicable and must not
  manufacture unsupported extension points.

### R7. Terminology consistency

- Each locale must define one generation-time terminology policy for core terms such as
  Evidence, Chunk, Index, Context, Provider, Corpus, and Skill.
- Localized guidance must require the localized term on first use with the canonical
  identifier where useful, then use one consistent form within a Page.
- Applicable templates must include a concise glossary/reference location; the CLI must
  not rewrite caller prose to enforce terminology.

### R8. Source version tracking

- Index identity must capture the Git HEAD commit when the repository is a Git worktree
  and whether indexed bytes came from a dirty worktree. Non-Git repositories use
  `null` commit and an explicit non-Git state.
- Wiki metadata must copy source version identity from the published index, not probe a
  potentially different repository state later.
- The final scope/version disclosure must show source commit, dirty/non-Git state,
  repository fingerprint, index build ID, and Wiki generation timestamp so a dirty
  build is never presented as the clean commit alone.

### R9. Compatibility and lifecycle

- These required structural and provenance fields ship in the already planned governed
  Wiki Schema `2.0`; this task must not add an intermediate persisted Schema `1.x`.
- Existing Schema `1.0` state remains byte-preserved and is never migrated implicitly.
  An explicit governed `wiki init` may replace it while preserving the last valid
  `wiki.md` until a successful build.
- Any Subsection title, description, order, direct source set, locale, terminology
  guidance, or source identity change invalidates only the affected Pages unless the
  existing governance matrix requires broader invalidation.
- No command may invoke a generative model or infer prose that was not supplied by the
  calling Agent.

### R10. Public contracts and documentation

- JSON mode remains one ANSI-free result document on stdout; diagnostics remain on
  stderr and existing exit-code categories remain unchanged.
- Executable help, Wiki Skill references, package resources, evaluation cases, and
  matched `docs/en/` and `docs/zh-CN/` documentation must describe the same structure,
  Evidence, locale, scope, and version contracts.

## Acceptance Criteria

- [ ] AC1: A governed structure round-trip preserves ordered Sections, Pages, and
  Subsections, rejects duplicate/unknown IDs and source paths, and includes all three
  levels in status and final contents links. (R1)
- [ ] AC2: The assembled AST contains exactly H1 Wiki, H2 Sections, H3 Pages, H4
  Subsections/framework blocks, and only H5/H6 caller headings; invalid submissions are
  rejected before persistence with bounded Subsection/line diagnostics. (R2)
- [ ] AC3: For each non-documentation-only Subsection, successful Evidence contains at
  least one complete item from every declared direct path and labels its direct role;
  submissions cite direct Evidence for each Subsection, and an insufficient budget fails
  before state mutation. (R3)
- [ ] AC4: Golden assembly tests for `en`, `zh-CN`, and `ja` prove exact localized
  framework and scope/version labels with no fallback. (R4)
- [ ] AC5: A built Wiki discloses the same scan mode, filters, effective defaults,
  counts, build ID, and fingerprint as the validated published index and does not
  replace the previous Wiki if the index changes during build. (R5)
- [ ] AC6: Applicable built-in templates and the Wiki Skill produce developer operation,
  extension, recovery, and glossary coverage backed by direct implementation Evidence.
  (R6, R7)
- [ ] AC7: Git clean, Git dirty, unborn/non-Git, and HEAD-change tests prove that index,
  metadata, status/build output, and final disclosure agree on source version identity.
  (R8)
- [ ] AC8: Schema `1.0` artifacts are preserved and rejected through the governed path;
  explicit `wiki init` creates the complete Schema `2.0` contract without replacing the
  old Markdown before a successful build. (R9)
- [ ] AC9: Reapplying identical structure/Evidence/page/build inputs is byte-idempotent,
  and source/outline changes invalidate only contract-affected Pages. (R9)
- [ ] AC10: Unit, integration, package smoke, evaluation, English/Chinese documentation,
  `make check`, and `make test-all` all cover and pass the new observable contracts.
  (R10)

## Out Of Scope

- Generating prose inside the CLI or adding an implicit model/Agent call.
- Arbitrary user templates, locale fallback, or locales beyond `en`, `zh-CN`, and `ja`.
- Historical Wiki snapshots, release tagging, changelog generation, or remote Git
  lookups.
- Exhaustively listing every Git-ignored file or reproducing private source content in
  the scope disclosure.
- Automatically rewriting terminology or malformed headings in caller prose.
- Improving general `search`/`context` ranking outside the direct Wiki Evidence contract.

## Open Questions

None. The implementation phase still requires explicit approval of the final planning
summary.
