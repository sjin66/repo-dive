# Template-governed Wiki CLI integration

## Goal

Expose the complete non-interactive classify/init/generate/validate/build workflow to
agents and CI with stable JSON, exit codes, package resources, and matched docs.

## Requirements

- Add `wiki classify`, `wiki init`, and read-only `wiki validate`.
- Return exact page contracts from `wiki evidence` under a required total generation
  token budget while retaining `--token-budget` as the requested Evidence sub-budget;
  surface governance in status/build.
- Return the standard error envelope plus exit `2` for `wiki validate`
  nonconformance, with bounded `valid:false` diagnostic details.
- Retain deprecated `wiki structure` for one release with strict governed behavior.
- Activate Schema `2.0` for init/evidence/page/build/status only when every required
  adapter is available; there must be no public intermediate state without an init
  path.
- Update package smoke, evaluation cases, help, AGENTS, and paired English/Chinese docs.

## Acceptance Criteria

- [ ] End-to-end tests cover all commands, locales, stdin/files, errors, and recovery.
- [ ] External validation always means one complete Wiki against persisted Schema
  `2.0`; page fragments remain exclusive to `wiki page`.
- [ ] Persisted validation checks structure and all generated bodies and, when
  complete, assembles in memory and checks exact locale, page order, citations, and
  source links. External validation performs the same complete-document checks against
  supplied bytes.
- [ ] Deprecated `wiki structure` initializes absent state only; every logical
  ID/order/localized title/description/relationship must match the composed template,
  while `relevant_files` may contain only current indexed paths.
- [ ] Generation guidance is reserved before Evidence, usage is reported separately,
  complete contracts are never truncated, Evidence receives
  `min(--token-budget, --generation-token-budget - guidance_tokens)`, and insufficient
  total budget fails before page state mutation.
- [ ] Schema `1.0` remains usable before this child and is rejected without byte changes
  after the complete Schema `2.0` command workflow is activated, except that explicit
  `wiki init` may replace it while preserving the old `wiki.md` until successful build.
- [ ] JSON mode emits exactly one document with no ANSI; diagnostics stay on stderr.
- [ ] Installed wheel/sdist contains and resolves every registered template resource.
- [ ] Fresh `make setup`, `make check`, and `make test-all` pass.

## Out of Scope

- Implicit model calls, custom templates, and Japanese developer documentation.

## Dependencies

- Wait for all four earlier children: classification, multilingual templates, AST
  validation, and governed Wiki state.
