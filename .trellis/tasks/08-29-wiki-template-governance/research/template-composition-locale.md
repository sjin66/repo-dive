# Research: Built-in template composition and locale parity

- **Query**: Design deterministic contracts for composed built-in templates and locale parity.
- **Scope**: mixed
- **Date**: 2026-08-29

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/repo_dive/wiki/models.py:153-287` | Current page/section/Wiki logical and ordered state model. |
| `src/repo_dive/wiki/models.py:290-335` | Metadata currently persists only repository/index identity and free-form output language. |
| `src/repo_dive/wiki/service.py:80-105` | Structure input currently lets callers supply all localized labels and any non-empty output language. |
| `src/repo_dive/wiki/service.py:196-220` | Output-language change currently invalidates all pages. |
| `src/repo_dive/wiki/assembler.py:20-53` | Assembler owns root, contents, section headings, and ordering. |
| `src/repo_dive/wiki/assembler.py:66-88` | Assembler owns page headings, related-page labels, and source labels around caller bodies. |
| `scripts/check_repo_contract.py:131-139` | Existing repository-doc parity check requires matching English/Chinese filenames. |
| `scripts/check_repo_contract.py:193-218` | Existing parity checks compare technical fenced blocks and README command lines. |
| `tests/unit/test_repo_contract.py:159-165,223-251` | Tests missing locale peers and technical-block parity. |
| `.trellis/tasks/08-29-wiki-template-governance/prd.md:48-76,86-98` | Bundled templates, closed contracts, locale parity, and governance identity requirements. |

### Ownership Boundary

The assembler inserts the root H1, contents H2, section H2, page H3, related-page H4, and sources H4 (`wiki/assembler.py:25-52,70-87`). Caller page bodies are inserted verbatim below an owned H3 (`wiki/assembler.py:70-76`). Therefore page contracts should govern only the body subtree below that H3; they must not ask the caller to reproduce the page heading, related-page block, or source block. Current documentation already says the caller must omit the page heading (`docs/en/wiki-workflow.md:124-128`).

### Candidate Registry Layers

Represent bundled templates as language-neutral machine contracts plus separate locale catalogs:

1. **Base**: exactly one primary archetype contribution.
2. **Topology overlay**: exactly one of `single_project`, `monorepo`, `microservices`.
3. **Facet additions**: zero or more, ordered by facet registry ordinal.
4. **Framework shell**: invariant CLI-owned nodes (`wiki`, `contents`, `related_pages`, `sources`) and page-body placement rules.

Each contribution contains stable logical section/page/node IDs, placement constraints, requiredness/cardinality, AST node constraints, evidence-query description, and instruction comments. Locale catalogs contain only display strings and instructional prose keyed by those logical IDs.

Candidate composed identity:

```json
{
  "template_schema_version": "1.0",
  "registry_version": "1",
  "primary_template_id": "cli_tool",
  "primary_template_version": "1",
  "topology": {"id": "single_project", "version": "1"},
  "facets": [{"id": "api", "version": "1"}],
  "locale": "zh-CN",
  "contract_sha256": "<hash of language-neutral composed contract>",
  "localized_sha256": "<hash of resolved localized generation contract>"
}
```

The two hashes distinguish validation-equivalent localization changes from logical contract changes while preserving exact generation guidance identity.

### Candidate Merge Algorithm

1. Start with the base contribution's ordered sections/pages.
2. Apply topology operations in declaration order, then facet contributions in registry order. Permit only closed operation kinds: `insert_before`, `insert_after`, `append_to_slot`, and `refine_existing`.
3. Resolve placement targets by logical ID, never localized heading text.
4. Reject the bundled registry at load time if a target is absent, IDs duplicate, placement dependencies cycle, or two contributions define the same ID without an explicit compatible `refine_existing` operation.
5. A refinement may only tighten declared constraints or add localized guidance; it cannot change a node's type or move it. This makes composition independent of incidental load order.
6. Extension slots are explicit nodes with allowed child types, min/max cardinality, heading-level policy, and insertion position. Any structure outside a slot or registered logical node is undeclared.
7. Serialize the fully resolved language-neutral contract with sorted object keys and preserved semantic arrays before hashing. Array order is contract order, not a set.

This yields one persisted contract even for hybrid repositories, as required by `prd.md:38-41,109-113`, without shipping every primary/topology/facet cross-product.

### Candidate Locale Parity Contract

- Registered first-release locale IDs are exactly `en`, `zh-CN`, and `ja` (`prd.md:86-90`). Use their canonical spelling and reject all other values; do not language-negotiate or fall back.
- RFC 5646 says language tags are case-insensitive but recommends registry casing (`zh-CN`) and locale-neutral casing. Because the product has a closed locale registry, accept only canonical registered IDs at the CLI boundary to avoid two persisted identities for the same locale.
- Every locale catalog must have exactly the same key set as the language-neutral registry: root labels, every section/page/node label, every enum display value, and every instruction key. Unknown and missing keys are package/registry validation failures.
- Locale values must be non-empty, trimmed UTF-8 strings. Logical IDs, requiredness, ordering, cardinality, AST node types, field formats, and extension-slot constraints exist only in the language-neutral contract and therefore cannot drift by locale.
- Resolve all labels before returning generation guidance. No fallback lookup is permitted; a missing localized string makes the bundled locale unavailable rather than producing mixed-language output.
- Validation matches AST nodes to persisted logical node positions/contract IDs, not translated heading text alone. Localized heading text is still checked against the exact catalog value when headings are template-owned.
- Instruction comments are generation-only metadata and are omitted when instantiating `wiki.json`, accepting page bodies, and assembling `wiki.md`, matching `prd.md:54-56`.

The repository's current documentation parity mechanism provides a useful precedent but is weaker: it checks paired filenames and selected fenced blocks (`scripts/check_repo_contract.py:131-139,193-218`), not key-complete locale catalogs.

### External References

- [RFC 5646 / BCP 47](https://www.rfc-editor.org/rfc/rfc5646.txt) — language tags are hyphen-separated, case-insensitive identifiers; Section 2.1.1 recommends conventional casing such as lowercase language and uppercase region.
- [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.txt) — deterministic object-key ordering and preserved array order are applicable to contract identity hashing.

### Related Specs

- No `.trellis/spec/**/*.md` files were found.
- `.trellis/tasks/08-29-wiki-template-governance/prd.md:48-98` — template, localization, and persistence requirements.

## Caveats / Not Found

- Current `output_language` accepts any non-empty unpadded string (`wiki/service.py:90-98`); there is no registered-locale enforcement.
- No package resources for templates/locales exist. The release harness currently verifies only `repo_dive/indexing/schema.sql` (`scripts/package_smoke.py:15-64`), so bundled template resources would need equivalent distribution coverage.
- CommonMark does not define tables; any template contract requiring tables must name a Markdown extension/profile explicitly.
