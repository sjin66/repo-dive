# Governed Wiki state lifecycle

## Goal

Persist exact classification/template/parser identity and enforce it throughout the
resumable Wiki lifecycle without destroying legacy or last-valid artifacts.

## Requirements

- Introduce strict Wiki and metadata Schema `2.0` with page-contract identity.
- Persist complete normalized composed/page contracts and exact parser identity.
- Initialize exact localized structures and invalidate only governance-affected pages.
- Validate submissions and final assembly before writes; preserve Evidence contracts.
- Reject Schema `1.0` as `wiki_template_state_missing` without modifying bytes.
- Serialize every Wiki mutation and build under one bounded repository-local lock.
- Permit `wiki init`, but not deprecated `wiki structure`, to explicitly replace
  legacy state; neither command replaces `wiki.md` before a successful build.

## Acceptance Criteria

- [ ] No-op init/update/build remains byte-idempotent.
- [ ] Identity and locale/parser changes follow the parent invalidation matrix.
- [ ] Invalid body/build/state never replaces valid persisted content or `wiki.md`.
- [ ] Localized framework labels and exact source anchors survive final validation.
- [ ] Concurrent valid page submissions are serialized and neither accepted update is
  lost; lock timeout/crash behavior is safe and tested.
- [ ] Existing public Schema `1.0` command dispatch remains unchanged until the final
  integration child activates all Schema `2.0` entry points together.

## Out of Scope

- Automatic migration or in-place repair of Schema `1.0` state.
- Public CLI activation of Schema `2.0`; this child provides independently tested
  internal services for the final integration child.

## Dependencies

- Wait for `08-29-repository-classification`, `08-29-multilingual-wiki-templates`, and
  `08-29-markdown-ast-validation`.
