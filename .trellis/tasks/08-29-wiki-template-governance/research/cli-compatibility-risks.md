# Research: Public CLI compatibility risks for template governance

- **Query**: Identify public CLI compatibility risks in deterministic Wiki template governance.
- **Scope**: internal
- **Date**: 2026-08-29

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/repo_dive/commands/wiki.py:46-128` | Current public Wiki subcommands and argument forms. |
| `src/repo_dive/commands/wiki.py:327-449` | Current JSON result fields. |
| `src/repo_dive/cli.py:64-80,95-126` | JSON-mode detection, command naming, and stdout/stderr behavior. |
| `src/repo_dive/schema.py:34-73` | Stable result/error envelope Schema `1.0`. |
| `src/repo_dive/errors.py:10-16,37-52` | Stable exit-code categories. |
| `docs/en/cli-contract.md:17-90` | Documented command/input/output contract. |
| `docs/en/cli-contract.md:421-471,494-502` | Stream, envelope, exit, idempotency, and compatibility rules. |
| `tests/integration/test_wiki_workflow.py:174-257` | Exact build JSON/Markdown and preservation expectations. |
| `tests/integration/test_wiki_structure.py:110-145` | Existing `wiki structure` command identity and Schema versions. |
| `tests/integration/test_wiki_evidence.py:147-205` | Existing evidence fields and Markdown output heading. |
| `tests/unit/test_repo_contract.py:22-30,45-62` | Repository documentation checks hard-code the current workflow names/lifecycle. |
| `scripts/package_smoke.py:15-23,45-93` | Packaged CLI smoke surface and sole required package data file. |

### Compatibility Risk Register

| Risk | Existing public anchor | Compatibility effect |
|---|---|---|
| Replacing `wiki structure` with `wiki init` | `commands/wiki.py:50-62`; docs `cli-contract.md:65-72`; `test_repo_contract.py:22-30` | Removing or changing required arguments is a breaking command change. Additive `wiki init` is safe; deprecating/removing `structure` requires an explicit command/version policy. |
| Making old Wiki commands reject valid Schema `1.0` state | `wiki/models.py:13-15`; `wiki/store.py:44-66` | Intentionally breaking persisted-state compatibility. PRD mandates stable `wiki_template_state_missing`, byte preservation, and explicit init rather than inference. |
| Adding required governance fields to Wiki/metadata `1.0` | `wiki/models.py:338-385` exact field sets | Impossible as a compatible optional-field extension; requires persisted Schema `2.0`. |
| Changing page submission shape | `wiki/submission.py:26-50`; docs `cli-contract.md:82-84` | The input is closed and exact. Requiring `template_contract_sha256` or locale in the same `1.0` input breaks callers; use submission Schema `2.0` or validate against persisted identity without a new caller field. |
| Returning template contract from `wiki evidence` | `commands/wiki.py:383-418` | Adding result fields is documented as backward compatible (`cli-contract.md:500-502`) if existing fields/types remain. Potentially large guidance must remain within explicit output/input budget policy. |
| Changing Markdown output prose/headings | `commands/wiki.py:452-523`; tests `test_wiki_evidence.py:201-205` | Markdown output is public raw stdout; tests assert headings. Localizing command-result Markdown or inserting template guidance changes consumers that parse current headings. JSON is the safer generation contract. |
| Validation failure exit semantics | `errors.py:10-16`; docs `cli-contract.md:464-471` | Mutating input conformance naturally maps to exit `2`; persisted missing governance maps to `3`; parser/runtime failures map to `4`. A standalone validator must document whether `valid:false` is exit `0` or `2`. |
| Diagnostic details disclose generated/source text | `schema.py:18-31`; `test_wiki_page.py:320-347,417-446` | Violates existing safe-error behavior. Diagnostics must use codes, IDs, counts, and locations only. |
| Reclassifying whenever source changes | `wiki/service.py:196-221`; `wiki/validation.py:55-72` | Could invalidate all pages where current behavior invalidates only stale Evidence. Identity comparison should distinguish changed audit signals from changed composed contract. |
| Localizing assembler-owned `Contents`, `Related pages`, `Sources` | `wiki/assembler.py:25-31,77-87`; exact test `test_assembler.py:95-135` | Changes persisted Markdown bytes/hash and exact outputs. Required for locale completeness, but observable and should be gated by governed Schema/locale identity. |
| Adding Markdown parser/default dependency | `pyproject.toml:13-17`; package smoke `scripts/package_smoke.py:69-93` | Changes install dependency surface and wheel contents. Must support Python 3.11+ and be present in default installs because Wiki validation is core, not an optional vector feature. |
| Shipping templates as package data | `scripts/package_smoke.py:15-64` | Source checkout may pass while wheel lacks templates. Wheel/sdist resource checks and installed-CLI smoke must enumerate registry/locales. |
| Adding `ja` docs under `docs/` | repository rule `scripts/check_repo_contract.py:131-139` | Product template locales and developer documentation locales are separate contracts. Repository instructions require matched English/Simplified-Chinese docs, not Japanese developer docs. |

### Candidate Additive CLI Surface

An additive surface that preserves current root behavior is:

```text
repo-dive wiki classify <repository> [--template ID] --format json|markdown
repo-dive wiki init <repository> [--template ID] --locale en|zh-CN|ja --format json|markdown
repo-dive wiki evidence <repository> --page ID --token-budget N --format json|markdown
repo-dive wiki page <repository> --page ID --input PATH|- --format json|markdown
repo-dive wiki validate <repository> [--input PATH|-] --format json|markdown
repo-dive wiki build <repository> --format json|markdown
repo-dive wiki status <repository> --format json|markdown
```

`classify` is read-only inspection. `init` is the sole explicit transition from absent/legacy state to governed state. Unknown template/locale values are invocation errors. `validate` is read-only. Existing `evidence/page/build/status` argument names can remain stable while their governed-state precondition changes as required by the PRD.

Candidate stable result additions:

- `classify`: full classification, matched signals, selected composed identity, available locale/template IDs.
- `init`: `changed`, created/invalidated/preserved IDs, classification, exact template/locale hashes and all Schema versions.
- `evidence`: retain every current field (`commands/wiki.py:400-418`) and add `locale`, `template`, and exact `page_contract`.
- `status`: retain current counts/page fields (`commands/wiki.py:343-380`) and add governance identity plus conformance status, never body content.
- `validate`: `valid`, exact identity, bounded ordered diagnostics, and validation target; no mutation metadata.
- `build`: retain current exact result fields (`commands/wiki.py:435-449`) and add optional template/locale/validation summary fields only if result Schema remains `1.0`.

### Stream and Error Invariants

All new functional commands must preserve one complete JSON document on stdout in JSON mode and diagnostics on stderr (`cli.py:95-126`; `docs/en/cli-contract.md:421-429`). Error codes remain stable machine identifiers while messages may change (`docs/en/cli-contract.md:449-462`). Markdown mode may emit raw Markdown, but JSON should be the canonical agent-facing contract because localized/generated Markdown is not a stable machine schema.

### Documentation and Test Coupling

The repository contract hard-codes the current workflow `structure -> evidence -> page -> build -> status` and command literals (`tests/unit/test_repo_contract.py:22-30,45-62`). Introducing `init`, `classify`, and `validate` changes executable help, English/Simplified-Chinese docs, AGENTS workflow, test fixtures, package smoke help coverage, and repository-contract literals together. Documentation must remain an English/Simplified-Chinese matched pair per repository instructions; template locale parity (`en`, `zh-CN`, `ja`) is a different runtime-resource rule.

### Related Specs

- No `.trellis/spec/**/*.md` files were found.
- `.trellis/tasks/08-29-wiki-template-governance/prd.md:77-103` — requested command surface, locale support, legacy behavior, and documentation pairing.

## Caveats / Not Found

- No deprecation policy exists for `wiki structure`; compatibility behavior must be decided before making `wiki init` canonical.
- No standalone validation command exit-status convention exists.
- Existing top-level result envelope remains Schema `1.0`; persisted artifact Schema and command-input Schema versions are independent and should not be conflated with it.
