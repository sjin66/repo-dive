# Markdown AST conformance validation

## Goal

Deterministically prove that page fragments and assembled Wikis satisfy their exact
persisted template contract before content is accepted or published.

## Requirements

- Parse with pinned `repo-dive-gfm-subset-1`: CommonMark 0.31.2 plus tables.
- Enforce declared hierarchy, order, node type/cardinality, minimum content, formats,
  comments/placeholders, code language, links, and extension slots.
- Return bounded, sorted, versioned diagnostics with safe one-based line ranges.
- Never render HTML, load dynamic plugins, or expose body/source excerpts.

## Acceptance Criteria

- [ ] Page, persisted-state, and final-document scopes use one pure validation engine.
- [ ] Every violation category has positive and negative fixtures.
- [ ] CRLF, nesting, large input, comments, malformed shapes, and truncation are tested.
- [ ] The parser dependency installs and passes Python 3.11+ package smoke tests.

## Out of Scope

- HTML sanitization, factual correctness, prose adequacy, and language detection.

## Dependencies

- Wait for `08-29-multilingual-wiki-templates`; this task consumes its node, slot,
  page-body, and complete localized framework-shell contracts.
