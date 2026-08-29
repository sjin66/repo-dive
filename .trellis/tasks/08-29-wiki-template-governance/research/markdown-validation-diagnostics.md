# Research: Markdown AST validation and diagnostic contract

- **Query**: Design deterministic Markdown validation diagnostics for template-governed Wiki content.
- **Scope**: mixed
- **Date**: 2026-08-29

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/repo_dive/wiki/submission.py:26-50` | Strict page submission Schema `1.0`. |
| `src/repo_dive/wiki/submission.py:53-82` | Current content checks cover UTF-8, NUL, byte bound, and evidence ownership only. |
| `src/repo_dive/wiki/service.py:365-428` | Submission validates freshness before content and persists failure codes on content failure. |
| `src/repo_dive/wiki/service.py:430-475` | Build validates page state/evidence then assembles and publishes atomically. |
| `src/repo_dive/wiki/assembler.py:20-53,66-88` | Defines the final Markdown node ownership and insertion positions. |
| `src/repo_dive/commands/wiki.py:282-324` | Bounded page JSON reading and stable version/input errors. |
| `src/repo_dive/schema.py:18-31,56-73` | Safe machine error details boundary. |
| `tests/integration/test_wiki_page.py:320-347` | Invalid page content does not disclose submitted private body. |
| `tests/integration/test_wiki_page.py:350-446` | Invalid UTF-8/oversize/surrogate handling and mutation behavior. |
| `tests/integration/test_wiki_workflow.py:218-257` | Build failures preserve the previous Markdown artifact. |
| `.trellis/tasks/08-29-wiki-template-governance/prd.md:60-76` | Required structural AST conformance and supported node classes. |

### Current Validation Boundary

Current page validation treats Markdown as an opaque string after checking non-empty/UTF-8/NUL/size (`wiki/submission.py:53-74`). No Markdown parser runtime dependency is present (`pyproject.toml:13-17`). The assembler inserts caller content verbatim between the page H3 and CLI-owned related/source H4 blocks (`wiki/assembler.py:70-87`). Tests enforce that rejected private body text does not appear in stdout/stderr (`test_wiki_page.py:320-347,417-446`) and that failed build does not replace the current artifact (`test_wiki_workflow.py:218-257`).

### Candidate Parsing Profile

Define and persist an exact parser profile, for example:

```json
{
  "markdown_profile": "repo-dive-gfm-subset-1",
  "commonmark_version": "0.31.2",
  "parser": "markdown-it-py",
  "parser_version_range": ">=4.0,<5.0",
  "enabled_extensions": ["table"],
  "raw_html": "forbidden"
}
```

CommonMark 0.31.2 defines block/inline precedence and headings, lists, fenced code, links, and raw HTML, but not tables. `markdown-it-py` documents a strict `commonmark` preset, source line maps on block tokens, a nested `SyntaxTreeNode`, and explicitly enabled table parsing. Because template rules require tables (`prd.md:71-74`), the profile must state the extension rather than claim pure CommonMark conformance.

Validate in three scopes:

1. **Page-body scope** on `wiki page`: parse the bounded body; reject parser/profile violations, instruction comments, duplicate/missing/misordered governed body nodes, heading escape above the page-body level, and node/cardinality/content constraints before persisting `generated`.
2. **State scope** on read-only `wiki validate`: validate persisted logical structure and every generated page body against the exact persisted contract without mutation.
3. **Document scope** on `wiki build` and external-document validation: assemble in memory, parse the full document, match CLI-owned and body-owned nodes to the composed contract, and only then atomically publish.

The same pure validator should return a complete deterministically sorted diagnostic list at all three boundaries. It should never render HTML; structural Markdown conformance is distinct from HTML sanitization, as current CLI docs already warn (`docs/en/cli-contract.md:88-90`).

### Candidate Structural Matching Rules

- Match headings by expected level, logical node position, and exact resolved localized title. Do not derive identity solely from slug generation.
- Treat body content as descendants of the CLI-owned page H3. A body H1-H3 is a hierarchy violation; expected governed subsections begin at H4 unless a page contract explicitly has no subsection headings.
- Count AST nodes, not source regex matches. Fenced code requires a non-empty declared info-string language when its node contract says so. Tables are table AST nodes under the named profile.
- Paragraph minimums count trimmed Unicode scalar values in text descendants after excluding markup and comments. This is a deterministic content bound, not a prose-quality judgment.
- Placeholder/instruction detection should be structural: forbid HTML comments in submitted bodies when bundled templates use comments for instructions, and forbid exact registered placeholder sentinel nodes. Do not use broad natural-language substring heuristics.
- Closed-by-default validation rejects unmatched nodes unless the current AST position is inside an explicit extension slot. Slots still define allowed node types, heading levels, and min/max counts.
- Inline constraints traverse inline child tokens for links/code spans/images. Link destination checks should be scheme/shape rules declared by the contract, not network access.
- Normalize CRLF/CR to parser line semantics only for location calculation; do not rewrite stored body bytes on successful validation.

### Candidate Diagnostic Shape

Return validation as a normal command result for `wiki validate` (including nonconformant documents), while `wiki page`/`wiki build` use a stable domain error whose details contain the same bounded diagnostics:

```json
{
  "valid": false,
  "template_contract_sha256": "<hash>",
  "diagnostic_count": 2,
  "diagnostics": [
    {
      "code": "markdown_required_node_missing",
      "severity": "error",
      "phase": "page_body",
      "page_id": "overview",
      "logical_node_id": "overview.runtime_flow",
      "instance_path": "/sections/0/pages/0/body",
      "start_line": null,
      "end_line": null,
      "expected": {"node_type": "heading", "min_count": 1},
      "actual": {"count": 0}
    }
  ]
}
```

Diagnostic fields are closed and versioned. Candidate stable codes:

- `markdown_parse_limit_exceeded`
- `markdown_node_undeclared`
- `markdown_required_node_missing`
- `markdown_node_duplicate`
- `markdown_node_misordered`
- `markdown_heading_level_invalid`
- `markdown_node_type_invalid`
- `markdown_cardinality_invalid`
- `markdown_content_too_short`
- `markdown_code_language_invalid`
- `markdown_field_format_invalid`
- `markdown_extension_slot_invalid`
- `markdown_instruction_comment_present`

Sort by phase ordinal, page/section contract ordinal, source start line (`null` last), logical node ID, then code. Locations are one-based inclusive, consistent with the repository-wide evidence convention (`docs/en/cli-contract.md:475-488`). Missing-node diagnostics have no source range. Never include body excerpts, heading text, code content, or parser exception text; current safe-error behavior intentionally returns IDs/counts rather than source (`wiki/submission.py:75-82`; `test_wiki_page.py:320-347`). Bound diagnostic count and report `diagnostics_truncated` plus total count when exceeded.

### Error and Mutation Semantics

- Malformed command options/input envelope/profile mismatch: invocation error, exit `2` (`errors.py:10-16,37-40`).
- Validly supplied external file or page body that is structurally nonconformant: invocation error for mutating `wiki page`; a read-only validation command may complete with exit `0` and `valid:false` if this is explicitly documented as its result contract.
- Missing/stale persisted governance state or evidence: repository error, exit `3` (`errors.py:43-46`).
- Parser crash/package resource failure after valid invocation: internal error, exit `4`.
- Page rejection must not persist invalid body. The current service marks page `failed` on content validation errors (`wiki/service.py:413-421`); retaining that lifecycle behavior is observable and should be an explicit compatibility choice.
- Build validates completely before `write_markdown` (`wiki/service.py:430-468`), preserving the current atomic-publication guarantee.

### External References

- [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) — unambiguous block/inline parsing model and conformance examples; every character sequence is a valid CommonMark document, so template violations are application-level diagnostics rather than Markdown syntax errors.
- [markdown-it-py usage](https://markdown-it-py.readthedocs.io/en/latest/using.html) — strict CommonMark preset, token source maps, nested syntax tree, and explicit table extension support.
- [JSON Schema 2020-12 Core](https://json-schema.org/draft/2020-12/json-schema-core) — Section 12 provides precedent for machine-readable validation output with instance and schema locations.

### Related Specs

- No `.trellis/spec/**/*.md` files were found.
- `.trellis/tasks/08-29-wiki-template-governance/prd.md:60-85` — mandatory validation and standalone command requirements.

## Caveats / Not Found

- CommonMark intentionally accepts all character sequences; a parser cannot itself label most input "invalid Markdown." Conformance rules must be defined by the template contract.
- `markdown-it-py` is not currently a dependency; its exact supported Python/version range and wheel inclusion need package verification before selection.
- Inline tokens generally do not carry source line maps as directly as block tokens; exact inline diagnostic columns would require additional source-position machinery. The candidate contract therefore requires line ranges, not columns.
