# Composed multilingual Wiki templates

## Goal

Provide detailed, built-in, versioned Markdown templates that compose one primary,
one topology, and ordered facets into an exact contract in `en`, `zh-CN`, and `ja`.

## Requirements

- Cover every parent taxonomy entry and all registered overlays.
- Keep validation rules language-neutral and localized labels/guidance key-complete.
- Explain every governed section with template comments; reject registry drift.
- Support only closed merge operations and explicitly declared extension slots.

## Acceptance Criteria

- [x] Every registered contribution resolves in all three locales with identical IDs.
- [x] Composition and hashes are deterministic and conflict/cycle detection is tested.
- [x] Guidance is detailed, placeholder-safe, and comments do not become output nodes.
- [x] Source-tree resource discovery can enumerate every registered resource; installed
  wheel/sdist verification remains owned by the final CLI integration child.

## Out of Scope

- User-authored templates and natural-language quality judgment.

## Dependencies

- Wait for `08-29-repository-classification`; this task consumes its final taxonomy
  IDs and ordering.
