# Template-governed multilingual Wiki generation

## Goal

Improve generated Wiki quality by classifying repositories, supplying detailed
project-type-specific Markdown templates to the calling Agent, and having the CLI
deterministically reject documents that do not conform to the selected template.

## Background

The current workflow can generate and atomically assemble `.repo-dive/wiki.md`, but
the calling Agent controls page prose and structure quality. The CLI validates page
state, Evidence ownership, Evidence freshness, and basic body bounds; it does not
currently persist a repository type or template identity, provide template guidance
at the generation boundary, or parse submitted Markdown for structural conformance.

The CLI must remain deterministic and must not invoke a generative model implicitly.
Interpretation and prose generation remain the responsibility of the calling Agent.

## Requirements

- R1. Define a documented, versioned classification taxonomy covering common
  repository types, including at least Web applications, data-science projects,
  command-line tools, SaaS applications, libraries/SDKs, microservices, desktop
  applications, infrastructure projects, mobile applications, embedded systems,
  and AI/ML projects, plus any additional types found necessary during design.
- R1a. The taxonomy is normalized by documentation need rather than represented as
  one flat set of mutually exclusive labels. Primary archetypes are Web application,
  service/API, CLI tool, library/SDK, data-science project, data pipeline, AI/ML,
  mobile application, desktop application, embedded/firmware, infrastructure,
  developer tool, plugin/extension, game, documentation/content, and general mixed.
  Topology overlays include single project, monorepo, and microservices. Facets
  include SaaS, multi-tenancy, UI, API, database, messaging, infrastructure, and
  model training/inference, with a versioned registry able to add further facets.
- R2. Classification must use deterministic local repository evidence and expose
  the selected type, matched signals, classifier version, and selection source in
  machine-readable output.
- R2a. Classification uses a compositional model: one primary project archetype
  selects the base template, repository topology contributes a topology overlay,
  and detected facets contribute additional governed sections. The composed result
  is persisted and validated as one deterministic template contract.
- R3. Users must be able to inspect classification and explicitly override automatic
  template selection with a known template identifier; unknown identifiers must be
  rejected as invocation errors.
- R3a. Automatic classification always yields a governing contract. A unique
  high-confidence result selects its primary template; weak, absent, or tied signals
  select `general_mixed`. The workflow remains non-interactive and repeatable.
- R3b. Classification output must distinguish the automatically detected primary from
  the effective primary template. An override changes only the effective primary and
  selection source; it does not erase detected scores, confidence, fallback reason,
  topology, facets, or signals.
- R4. Provide a detailed, versioned Markdown template for every supported project
  type. Templates must contain comments that explain the purpose, required content,
  ordering, cardinality, and validation rules for every governed section.
- R4a. The first release supports only templates bundled and versioned with the CLI.
  Users may select a registered template ID but may not load user-authored template
  files. Custom template schemas and trust boundaries are deferred.
- R4b. Instructional comments are present in bundled templates and generation-facing
  contracts but are not persisted into generated page prose or the final Wiki.
  Any HTML comment and exact registered placeholder sentinel
  `{{repo_dive:<logical-id>}}` in submitted content are template violations; no
  open-ended natural-language placeholder heuristic is permitted.
- R5. Template contracts must be available to the calling Agent at the
  context-to-generation boundary so generated page content can conform before it is
  submitted.
- R5a. `wiki evidence` must account for complete template guidance separately from
  Evidence. `--generation-token-budget` is the total hard ceiling and
  `--token-budget` remains the requested Evidence sub-budget. Complete guidance is
  reserved first; Evidence receives the smaller of its requested budget and the total
  remainder. The response reports both budgets and usages, never truncates the
  contract, and fails before mutation when guidance leaves no Evidence capacity.
- R6. Wiki structure, submitted page bodies, and the final assembled document must
  be validated deterministically against the persisted template contract. Markdown
  must be parsed structurally rather than checked by regular expressions or Agent
  judgment.
- R7. Conformance is mandatory: missing, duplicate, misordered, or otherwise invalid
  governed nodes must prevent persistence/publication and return stable, safe,
  machine-readable diagnostics.
- R7a. Template contracts are closed by default: undeclared sections and pages are
  rejected. A template may declare explicit extension slots; project-specific content
  is accepted only inside those slots and remains subject to AST hierarchy, ordering,
  uniqueness, and slot-specific constraints.
- R7b. In addition to exact heading structure, deterministic validation enforces the
  template-declared node types and cardinalities for paragraphs, lists, tables, code
  blocks, links, anchors, and other supported Markdown nodes; minimum non-placeholder
  content bounds; code-fence language and declared-field formats; and extension-slot
  constraints. It does not claim to validate factual accuracy, explanatory adequacy,
  or subjective natural-language quality.
- R8. Add non-interactive CLI commands for template-governed Wiki generation support
  and standalone validation. Every functional command must support `--format json`,
  keep stdout to one JSON document in JSON mode, and use existing exit-code rules.
- R8a. `wiki init` deterministically classifies the repository and instantiates the
  localized composed Wiki structure. `wiki evidence` returns source Evidence plus the
  exact page contract. The calling Agent generates prose. `wiki page` validates and
  persists a submission. `wiki validate` performs read-only conformance checks for
  persisted state or external Markdown. `wiki build` revalidates and atomically
  assembles `.repo-dive/wiki.md`.
- R8b. The existing `wiki structure` command remains available for one release cycle
  and is documented as deprecated. It retains its existing input form, automatically
  classifies the repository, and may create Schema `2.0` only when no Wiki state
  exists. Its logical section/page IDs, order, localized titles/descriptions, and
  relationships must exactly match the selected composed template; `relevant_files`
  remains a caller-supplied list of current indexed paths. It rejects Schema `1.0`
  with `wiki_template_state_missing` and never creates ungoverned state.
- R8c. `wiki validate` returns exit code `0` only for a conformant target. A
  structurally nonconformant but readable target returns exit code `2` using the
  existing JSON error envelope; safe details contain `valid: false` plus bounded
  diagnostics. This remains an input validation failure under the global exit-code
  contract rather than introducing a successful result with a failure exit status.
- R8d. Without `--input`, `wiki validate` validates persisted Schema `2.0` structure,
  all generated page bodies, and the in-memory final document when the Wiki is
  complete. With `--input PATH|-`, it validates one complete assembled Wiki document
  against the persisted Schema `2.0` contract, locale, page order, citations, and
  source links. It never treats external input as a page fragment; page fragments are
  validated only by `wiki page`.
- R9. Support multiple output languages. Each localized template must preserve the
  same language-neutral logical IDs, requiredness, ordering, and validation rules;
  unsupported languages must not silently produce mixed-language output.
- R9a. The first release must ship complete template localizations for `en`,
  `zh-CN`, and `ja`. Other locale identifiers must be rejected until registered.
- R10. Persist repository classification, template ID/version, classifier version,
  locale, and selection source so changes can deterministically invalidate affected
  generated state.
- R10a. Existing Schema `1.0` Wiki state without template governance is not inferred
  or automatically migrated. Governance-aware commands return the stable
  `wiki_template_state_missing` repository error without modifying existing
  state. A user must run `wiki init` explicitly; the last valid `.repo-dive/wiki.md`
  remains untouched until a newly governed Wiki builds successfully.
- R10b. Persist the complete normalized composed contract and exact page contracts,
  not hashes alone, plus contract/guidance hashes, parser profile, parser package, and
  exact parser version. Validation must never depend on an older bundled registry
  remaining installed.
- R11. Preserve the existing resumable Evidence workflow, citation validation,
  atomic `wiki.md` publication, repository-relative POSIX paths, and one-based
  inclusive source ranges.
- R12. User-facing and developer-facing documentation must be updated in matched
  English and Simplified Chinese pairs.
- R13. Wiki mutations and builds must use a repository-local exclusive lock covering
  read, validation, and publication. A concurrent mutation must wait within a bounded
  timeout or fail safely without writing; two valid page submissions must not silently
  overwrite each other.

## Acceptance Criteria

- [ ] A versioned taxonomy and template registry enumerate every supported type and
  locale, with a deterministic fallback for unclassified repositories.
- [ ] Classification fixtures demonstrate deterministic selection, auditable signals,
  explicit override, unknown/fallback behavior, and mixed or monorepo behavior.
- [ ] Hybrid and monorepo fixtures prove that primary type, topology, and facets
  compose deterministically without requiring a separate template for every possible
  combination.
- [ ] Every registered project type has a detailed template whose comments and
  machine contract describe all governed sections.
- [ ] Generation-facing CLI output includes the exact persisted template identity and
  complete requirements needed by the calling Agent, with explicit guidance/Evidence
  budget accounting.
- [ ] Valid localized documents are accepted, while tests prove that each structural
  violation class is rejected before invalid content can replace a valid artifact.
- [ ] Undeclared structure is rejected, while content in declared extension slots is
  accepted only when it satisfies the slot contract.
- [ ] A standalone validation command reports conformance without mutating Wiki state.
- [ ] Automation can block on `wiki validate` exit status: conformant targets return
  `0`, while nonconformant targets return `2` with the standard error envelope,
  machine-readable diagnostics, and no state mutation.
- [ ] Template, locale, or classifier-governance changes invalidate affected state in
  a documented and tested manner.
- [ ] Legacy ungoverned state is preserved byte-for-byte on compatibility errors and
  explicit reinitialization does not replace the last valid Markdown artifact.
- [ ] English, Simplified Chinese, and Japanese templates produce fully localized
  framework labels while enforcing equivalent logical contracts.
- [ ] Existing JSON isolation, bounded input, resumability, Evidence freshness,
  atomicity, and idempotency contracts remain covered by regression tests.
- [ ] Contract snapshots remain valid across registry upgrades, parser changes trigger
  deterministic invalidation, and concurrent writers cannot lose accepted page state.
- [ ] `make check` and `make test-all` pass from a freshly prepared environment.

## Out of Scope

- The CLI judging subjective prose quality, factual completeness, or writing style.
- The CLI detecting whether arbitrary prose is truly written in the requested natural
  language; it validates locale identity and localized structural contracts only.
- Implicit calls to a generative model.
- Treating structural Markdown conformance as HTML sanitization or execution safety.
- Loading or executing user-authored template files.

## Confirmed Constraints

- Existing Wiki state and metadata use strict Schema `1.0`; adding governance identity
  requires an explicit compatibility or schema-version decision in technical design.
- The assembler owns Wiki, section, and page headings plus related-page and source
  blocks; page templates must account for those generated nodes.
- There is no current Markdown AST runtime dependency. Dependency choice and package
  inclusion require explicit technical justification and Python 3.11+ support.
- Changing `output_language` already invalidates generated pages, providing a
  behavioral precedent for template-governance changes.

## Delivery Map

- `08-29-repository-classification`: deterministic primary/topology/facet classifier.
- `08-29-multilingual-wiki-templates`: composed built-in contracts and `en`,
  `zh-CN`, and `ja` Markdown resources.
- `08-29-markdown-ast-validation`: fixed Markdown profile, AST validation, and safe
  diagnostics.
- `08-29-governed-wiki-state`: Schema `2.0`, governance persistence, invalidation,
  and legacy-state preservation.
- `08-29-wiki-template-cli-integration`: command integration, package resources,
  end-to-end tests, and paired English/Simplified-Chinese documentation.
