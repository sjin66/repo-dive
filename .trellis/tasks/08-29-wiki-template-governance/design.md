# Design: Template-governed multilingual Wiki generation

## Architecture

The feature adds four deterministic domain components behind the existing Wiki
application service:

```text
published index
  -> repository classifier
  -> template composer + locale resolver
  -> governed Wiki Schema 2.0
  -> Evidence + generation contract
  -> caller-generated Markdown
  -> Markdown AST validator
  -> governed state persistence
  -> final AST validation + atomic wiki.md build
```

CLI modules continue to own only arguments, process output, and exit behavior.
Classification, composition, parsing, validation, invalidation, and persistence remain
typed domain services. No layer invokes a generative model.

## Repository Classification

Add a focused `repo_dive.classification` package with immutable models, a bundled rule
registry, and one service over a validated `PublishedIndex`.

The result is a closed Schema `1.0` document containing classifier/taxonomy versions,
repository and index identity, detected primary/scores/confidence/fallback reason,
effective primary, selection source, topology, ordered facets, matched signal
IDs/weights/paths, and optional template override. Rules use bounded matcher kinds
only: exact path, path glob, language count/ratio, and parsed key/value signals from
named manifests. They never scan arbitrary prose or ignored files.

Scores are integers. A primary must meet both a threshold and a margin over the
runner-up; otherwise `general_mixed` is selected. Ties never use registry order as a
semantic tiebreaker. Exactly one topology is selected, and every facet meeting its
threshold is emitted in registry order. Explicit overrides change only the effective
primary template and selection source; the detected result, topology, facets, and
signals remain auditable.

## Template Registry And Composition

Template resources are bundled under `repo_dive/wiki/templates/` and consist of:

- a language-neutral, versioned contract registry for primary, topology, facet, and
  framework-shell contributions;
- detailed localized Markdown guidance resources for `en`, `zh-CN`, and `ja`;
- exact locale catalogs for assembler-owned labels and contract display text.

Logical IDs are ASCII and locale-neutral. Exactly one primary contribution is applied,
then one topology contribution, then facets in registry order. Supported merge
operations are closed to `insert_before`, `insert_after`, `append_to_slot`, and
constraint-tightening `refine_existing`. Composition rejects missing targets,
duplicates, cycles, incompatible refinements, or locale key drift before serving a
contract.

Each template declares ordered Wiki sections/pages and each page-body subtree. Node
constraints cover type, heading level, cardinality, ordering, minimum content, field
format, code-fence language, and extension slots. Resources contain detailed HTML
comments explaining purpose and requirements. These comments are generation guidance,
not accepted output nodes. Submitted HTML comments are forbidden. The only registered
placeholder syntax is the exact ASCII sentinel `{{repo_dive:<logical-id>}}`; validators
do not guess placeholders from translated or natural-language text.

The composed identity persists registry and contribution versions, canonical locale,
the SHA-256 of the language-neutral contract, and the SHA-256 of localized guidance.
Changing localized prose without changing validation rules can therefore be
distinguished from a logical contract change. The complete normalized composed
contract and page contracts are also persisted in Wiki state, so later validation does
not require an old registry version to remain installed.

## Markdown Profile And Validation

Add the core dependency `markdown-it-py>=4.2,<4.3`. Construct exactly one parser profile:

```python
MarkdownIt("commonmark", {"html": True}).enable("table")
```

The profile is named `repo-dive-gfm-subset-1`, aligned to CommonMark 0.31.2 with only
the table extension enabled. Governance identity records this profile, the parser
package, and the exact installed parser version. A parser-version change is a
governance change and forces deterministic revalidation/invalidation before new page
content is accepted. HTML is tokenized solely to identify and reject comments or
undeclared raw HTML; validation never renders HTML or loads plugins dynamically.

One pure validator handles three scopes:

1. Page body: validates a submitted fragment below the CLI-owned H3 page heading.
2. Persisted state: validates every generated page against its persisted page contract.
3. Final document: validates CLI-owned shell nodes and body nodes after in-memory
   assembly and before publication. External input is always treated as one complete
   assembled Wiki and matched against persisted Schema `2.0` page order, locale,
   citations, and source links; it is never interpreted as a page fragment.

Diagnostics use a closed Schema `1.0`, stable codes, phase, page/logical IDs, instance
path, one-based inclusive block line range, and bounded expected/actual summaries.
They never include body excerpts, source content, raw parser exceptions, or secret
values. Missing nodes have null ranges; inline violations cite their enclosing block.
Ordering is deterministic and output is capped with explicit truncation metadata.

## Governed State Schema

Wiki and metadata move to strict Schema `2.0`. Metadata persists complete classifier
and composed-template identity, canonical locale, parser profile/package/version,
repository/index identity, and timestamps. Wiki state persists the complete normalized
composed contract and each exact page contract, in addition to their identities and
hashes. Page submission can remain envelope-compatible by validating against persisted
contracts; a new caller-supplied hash is not required.

Valid Schema `1.0` state has no inferable governance identity. Governance-aware reads
return `wiki_template_state_missing` with exit code `3` and preserve all bytes. `wiki
init` is the only command that may explicitly replace legacy state with a new governed
structure. Deprecated `wiki structure` may initialize only when state is absent and
must reject legacy state. Neither path replaces the last valid `wiki.md`.

Invalidation compares identities rather than timestamps:

- changed audit signals with identical composed identity preserve pages;
- primary/topology/facet or logical-contract changes invalidate affected pages;
- locale changes invalidate all pages;
- localized guidance changes invalidate only pages whose generation guidance changed;
- parser/page-contract changes invalidate pages governed by changed contracts;
- changed source invalidates only pages whose Evidence is stale when governance is
  unchanged;
- no-op init/override/build performs no write.

All mutating Wiki commands and `wiki build` acquire a repository-local exclusive OS
file lock before reading state and retain it through validation and publication. Lock
acquisition has a bounded timeout and a stable repository error; it never steals a
live lock. This makes read-modify-write state transitions single-writer and prevents
concurrent page updates from erasing one another. Existing separate atomic JSON writes
retain the current detectable incomplete-state behavior. Every operation builds and
validates complete documents in memory before writing, and `wiki.md` remains
independently atomic and is changed only by successful `wiki build`.

## CLI Contracts

The additive command surface is:

```text
repo-dive wiki classify <repository> [--template ID] --format json|markdown
repo-dive wiki init <repository> [--template ID] --locale en|zh-CN|ja --format json|markdown
repo-dive wiki evidence <repository> --page ID --token-budget N --generation-token-budget N [--max-results N] --format json|markdown
repo-dive wiki page <repository> --page ID --input PATH|- --format json|markdown
repo-dive wiki validate <repository> [--input PATH|-] --format json|markdown
repo-dive wiki build <repository> --format json|markdown
repo-dive wiki status <repository> --format json|markdown
```

`classify` and `validate` are read-only. `init` instantiates the exact localized
structure. Evidence JSON retains all existing fields and adds locale, composed
identity, and the exact page contract plus detailed Markdown guidance. The required
generation budget is the total hard ceiling, while `--token-budget` remains the
requested Evidence sub-budget. Let `G` be complete guidance tokens and `T` the total
generation budget; if `G >= T`, the command fails before mutation. Otherwise Evidence
is packed under `min(--token-budget, T - G)`. The response reports requested Evidence,
applied Evidence, guidance, and total usage; guidance is never truncated. JSON remains
the canonical calling-Agent interface.

`wiki validate` returns a normal result document only when valid. Nonconformance is an
input validation error with exit code `2` and the existing error envelope; bounded
details contain `valid:false`, target identity, and diagnostics. This preserves the
global rule to inspect exit status before consuming a result. Mutating `wiki page` and
`wiki build` use the same diagnostic detail contract and never persist invalid
bodies/artifacts.

`wiki structure` remains for one release as deprecated. It uses its existing input
shape and output-language field, but initializes only absent state. Logical IDs,
order, localized titles/descriptions, and relationships must equal the composed
template; only valid indexed `relevant_files` remain caller-selected. It rejects
Schema `1.0` and never creates new ungoverned state.

## Localization

Locale IDs are exactly `en`, `zh-CN`, and `ja`; no normalization, negotiation, or
fallback occurs. Locale catalogs must have identical key sets. Validation rules live
only in the language-neutral contract, while exact localized template-owned headings
are validated against the selected catalog. Assembler-owned `Contents`, related-page,
and source labels are localized from the same registry.

Developer documentation remains paired under `docs/en/` and `docs/zh-CN/` according
to repository policy. Japanese is a runtime template locale, not a third developer-doc
tree.

## Security And Bounds

- Classification uses only the current validated index and bounded named manifests.
- Markdown and template input retain explicit byte limits; parser nesting remains
  bounded and diagnostics are capped.
- Detailed generation guidance and Evidence are admitted only under the explicit
  generation token budget; complete contracts are never truncated.
- Parsing never renders or executes HTML, code fences, links, or template content.
- User-authored templates and dynamic parser plugins are not supported.
- External Markdown validation reads bounded UTF-8 from a file or stdin and does not
  mutate repository state.

## Packaging And Compatibility

Wheel and sdist smoke tests must prove that every contract, locale, and Markdown
resource is installed. The new Markdown parser is a required dependency because Wiki
conformance is core behavior. Existing JSON result fields remain stable where
possible; additive governance fields are allowed. Persisted state deliberately uses a
new major schema because mandatory governance fields cannot be represented safely in
Schema `1.0`.

## Rollback

Code rollback leaves activated Schema `2.0` state unreadable by the old binary, but the
last successfully built `wiki.md` remains stable. No migration rewrites Schema `1.0`
in place. Children 1-4 add tested domain capabilities without switching the public
Schema `1.0` command path; child 5 is the single activation point for Schema `2.0` and
must ship atomically with all command adapters, package resources, tests, and docs.

## Sources

- `.trellis/tasks/08-29-wiki-template-governance/research/classification-contract.md`
- `.trellis/tasks/08-29-wiki-template-governance/research/template-composition-locale.md`
- `.trellis/tasks/08-29-wiki-template-governance/research/markdown-validation-diagnostics.md`
- `.trellis/tasks/08-29-wiki-template-governance/research/schema-state-invalidation.md`
- `.trellis/tasks/08-29-wiki-template-governance/research/cli-compatibility-risks.md`
- `.trellis/tasks/08-29-wiki-template-governance/research/python-markdown-parser-comparison.md`
- https://spec.commonmark.org/0.31.2/
- https://github.github.com/gfm/
- https://markdown-it-py.readthedocs.io/en/latest/using.html
- https://markdown-it-py.readthedocs.io/en/latest/security.html
- https://www.rfc-editor.org/rfc/rfc5646.txt
