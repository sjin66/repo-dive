# Design: Structured, localized, provenance-aware Wiki output

## Architecture And Sequencing

Implement this task as an extension of the governed Wiki Schema `2.0` activation planned
by `08-29-wiki-template-governance`. Do not evolve the deprecated public Schema `1.0`
models independently. The activation boundary must contain all required structure,
validation, localization, Evidence, and provenance adapters before any Schema `2.0`
state is publicly writable.

```text
published index + source identity + corpus policy
  -> repository classification
  -> localized template composition
  -> Section / Page / Subsection governed structure
  -> direct-source reservation + fused supplemental retrieval
  -> page contract + Evidence bundle
  -> caller-generated subsection content
  -> Markdown AST validation
  -> governed state persistence
  -> localized assembly + scope/version disclosure
  -> final AST/freshness validation
  -> atomic wiki.md publication
```

CLI modules remain argument/result adapters. Index provenance belongs to indexing,
outline and lifecycle state belong to Wiki models/services, locale labels belong to the
template registry, Markdown shape belongs to validation/assembly, and prose remains the
calling Agent's responsibility.

## Governed Structure Contract

Add an immutable `Subsection` contract below each Page. Its public logical fields are:

```text
id: stable lower-snake-case locale-neutral identifier
title: exact localized display title
description: focused generation and retrieval purpose
direct_source_paths: ordered repository-relative indexed paths
documentation_only: explicit built-in contract flag
```

`documentation_only` is controlled by a built-in composed contract, not freely asserted
by page submission. A normal Subsection requires one or more direct paths; a
documentation-only Subsection may rely on formal documentation Evidence. Persist the
complete normalized Subsection contracts and their hashes with each Page so subsequent
validation does not depend on the currently installed registry.

The existing template `heading` node becomes an explicit Subsection rather than an
anonymous cardinality allowance. Primary resources define the base Subsections;
topology/facet contributions may insert or tighten them through existing composition
operations. Exact locale catalogs resolve titles without changing logical IDs.

`wiki status` projects Subsection IDs/titles and generation completion under each Page,
but Page remains the lifecycle, retrieval, invalidation, and retry unit. This avoids a
second nested state machine while making the generation outline explicit.

## Heading And Submission Contract

The framework owns all headings through H4:

```text
H1 Wiki
H2 Section
H3 Page
H4 Subsection
H5/H6 caller detail (optional)
H4 Related pages (optional)
H4 Sources
```

Schema `2.0` Page submission replaces the monolithic body with one exact ordered entry
per persisted Subsection:

```text
subsection_id: exact contract ID
body: non-empty Markdown below the H4 heading
evidence_ids: non-empty Evidence IDs cited by this Subsection
```

The Page remains the single submission and lifecycle unit: partial Subsection writes are
not accepted. Persist immutable ordered Subsection content records so retries and
invalidation remain atomic at Page scope. Each non-documentation-only record must cite
at least one direct Evidence item whose coverage includes its Subsection ID.

Use the governed Markdown AST validator rather than regular expressions. Validate each
body fragment below its contract-owned H4. H1-H4 are rejected; H5/H6 are allowed. The
diagnostic identifies the Page, Subsection, and fragment-relative one-based block lines.

Assembly emits the stable
`subsection-<sha256(page_id + NUL + subsection_id)>` anchor, exact localized H4 heading,
then the validated fragment. It does not rewrite caller content. Contents links target
these anchors.

Related/Sources remain assembler-owned H4 siblings and cannot collide with a Subsection
logical ID or localized title. The final complete-document AST validation confirms the
shell, exact outline order, and source links before publication.

## Direct Evidence Selection

Separate mandatory direct Evidence from ordinary ranking without bypassing the existing
Evidence identity and freshness model.

1. Load the validated published index once.
2. Run normal lexical/structural/optional-vector retrieval for the complete Page query,
   including Subsection titles, descriptions, and source paths.
3. For each declared direct path, select the highest-ranked complete Chunk from that
   path. If normal candidate limits omitted the path, run a bounded path-scoped lexical
   selection over that file's indexed Chunks; deterministic ties use symbol presence,
   score, line range, and Chunk ID.
4. Deduplicate mandatory Chunks by Chunk ID while retaining every satisfied path.
5. Reserve envelope metadata and all mandatory direct Chunks first. If they do not fit,
   return `wiki_evidence_direct_budget_insufficient` with bounded counts and required
   minimum tokens before any Page write.
6. Fill the remaining budget with existing fused candidates under diversity and
   complete-Chunk rules.

Extend Evidence item output with an additive role (`direct` or `supplemental`) and the
Subsection IDs/direct paths it satisfies. Persist role/coverage with the Evidence
snapshot so page generation, status, and later validation can prove the requirement was
met. Citation IDs remain the same stable IDs and all Evidence goes through current hash,
path, line, and freshness checks.

Do not globally change `EvidencePacker` semantics for ad hoc Context. Add a Wiki-specific
reservation layer that supplies the remaining ranked candidates to the existing packer
or a narrowly extended pack API with default behavior unchanged.

## Corpus Scope And Source Identity

Index provenance is captured when an index generation is built, because a later Wiki
command could observe a different HEAD/worktree than the indexed bytes. Extend the index
manifest's next compatible schema with:

```text
source_control: git | non_git
source_commit: full lowercase Git object ID | null
source_dirty: bool | null
effective_default_excluded_directories: sorted strings
```

For Git repositories, read HEAD and dirty state using bounded non-interactive Git
commands during candidate discovery/index preparation. An unborn HEAD has a null commit
and dirty state reflecting indexed files. For non-Git repositories both source commit
and dirty state are null and source control is explicit. Git probe failures that would
make identity ambiguous fail indexing safely rather than inventing a clean version.

Wiki metadata copies this immutable source identity from the published manifest whenever
governed state is initialized or updated to a new index. It does not run Git itself.
Repository fingerprint remains the exact content/policy identity; commit is explanatory
base-version context, especially when `source_dirty` is true.

Build constructs a typed `WikiBuildContext` from the same validated published index and
persisted metadata. It contains locale labels, corpus policy, counts, source identity,
build ID, fingerprint, and the persisted Wiki update timestamp. The pure assembler
accepts `Wiki` plus this context. After in-memory assembly and AST validation, the
service reloads the published index and compares build/fingerprint/source identity before
atomic publication.

The localized scope/version block appears after the Wiki description and before
Contents. It reports policy and aggregate metadata only, never private source excerpts
or an exhaustive ignored-file list.

## Localization And Terminology

Extend the closed locale catalog with IDs for scope/version labels and terminology
guidance. The same exact persisted catalog used by validation is passed to assembly;
there is no assembler-local translation table and no fallback.

Each locale resource includes a concise terminology policy for canonical terms. Built-in
templates add a glossary/reference Subsection where applicable. Validation enforces
structural presence, not natural-language wording; automatic prose rewriting would
violate the caller-generation boundary.

## Developer Guidance

Update software-oriented primary contracts, especially `cli_tool` and
`developer_tool`, so their page/subsection outlines cover:

- prerequisites, installation, and first successful command;
- common commands and configuration;
- local setup and the repository's canonical check/test/package entry points;
- evidenced parser, retriever, and Provider extension boundaries;
- stable errors, recovery, and troubleshooting;
- glossary and scope/version interpretation.

Update all `en`, `zh-CN`, and `ja` runtime resources together. Update only the matched
English/Chinese developer documentation pair. The Wiki Skill should consume exact
governed outlines when available and retain a compatible manual-structure instruction
only for the still-shipped deprecated command.

## Invalidation And Compatibility

The Page contract hash includes ordered Subsection identities, localized titles,
descriptions, direct paths, documentation-only flags, and generation guidance. A changed
hash invalidates that Page. Locale changes invalidate all Pages. Changed index source
identity invokes existing stale-Evidence analysis; disclosure-only timestamp changes do
not independently invalidate generated prose.

Schema `1.0` remains readable only through the existing legacy behavior until governed
Schema `2.0` activation. After activation, governance-aware commands reject legacy state
without byte changes. Explicit `wiki init` may replace legacy JSON state, but never the
last built Markdown; only a successful governed build replaces `wiki.md`.

Because structure and provenance are mandatory, no dual-read optional-field shim is
added to Schema `2.0`. This avoids persisted states that claim governance while lacking
the outline or version needed to validate output.

## Errors And Observability

Use existing exit categories and result envelopes. Add stable bounded diagnostics for:

- invalid or duplicate Subsection contracts;
- unknown/unindexed direct paths;
- required direct Evidence budget insufficiency;
- missing, reordered, duplicate, or wrong-level Subsection headings;
- index/source identity changes during build.

JSON mode remains the canonical Agent interface. Status/build JSON add source identity,
scope summary, and Subsection counts without embedding private body text.

## Security And Bounds

- All direct paths pass the existing repository-relative POSIX and current-index checks.
- Path-scoped retrieval is bounded by declared paths, indexed Chunk count, result count,
  and token budget; it never reads outside the published index.
- Git probes use fixed argument arrays, no shell, bounded captured output, and safe
  diagnostics.
- Scope/version output contains metadata only and does not expose environment variables,
  credentials, ignored file contents, or raw Git errors.
- Markdown parsing remains bounded by existing body byte, parser nesting, and diagnostic
  limits; assembly never renders or executes HTML.

## Rollout And Rollback

Ship this change only with the complete governed Schema `2.0` command family and updated
package resources. Before activation, domain components can land behind internal tests.
Activation must prove a fresh `wiki init -> evidence -> page -> validate -> build`
workflow for every locale.

Rollback may remove the new executable path but must not rewrite Schema `2.0` state or
delete the last valid `wiki.md`. A rolled-back binary reports unsupported state; users
retain the published Markdown and can reinstall the compatible version.
