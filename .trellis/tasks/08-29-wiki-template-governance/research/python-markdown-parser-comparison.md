# Research: Python Markdown parsers for deterministic structural validation

- **Query**: Compare maintained Python 3.11+ Markdown parsers suitable for deterministic CommonMark/GFM AST/token inspection, especially markdown-it-py and alternatives; cover API shape, tables, fenced code, HTML comments, source positions, extensions, dependencies, licensing, packaging, security, and recommend one for this pure-Python CLI.
- **Scope**: mixed
- **Date**: 2026-08-29

## Findings

### Repository Context

| File Path | Description |
|---|---|
| `.trellis/tasks/08-29-wiki-template-governance/prd.md:49-75` | Bundled templates contain instructional HTML comments; submitted Markdown must be parsed structurally and checked for node types/cardinality. |
| `.trellis/tasks/08-29-wiki-template-governance/prd.md:139-150` | Structural validation is not HTML sanitization; the project is Python 3.11+ and currently has no Markdown AST dependency. |
| `pyproject.toml:5-17` | `repo-dive` requires Python `>=3.11`, uses an MIT license, and currently has only tree-sitter runtime dependencies. |
| `AGENTS.md` | Product boundary requires deterministic local processing, minimal justified runtime dependencies, bounded input, and no implicit model calls. |

No Markdown parser is currently present in product code or dependency metadata.

### Shortlist at 2026-08-29

Published versions and Python constraints below come from each project's PyPI JSON metadata on the research date; repository default branches can be ahead of the latest release.

| Parser | Current release | Dialect and inspection API | Runtime footprint on Python 3.11 | License | Fit summary |
|---|---:|---|---|---|---|
| **markdown-it-py** | 4.2.0 (2026-05-07), Python `>=3.10` | CommonMark 0.31.2; `MarkdownIt.parse()` returns typed flat `Token` objects, and `SyntaxTreeNode(tokens)` creates a tree | Pure Python plus `mdurl~=0.1`; no GFM-table extra is needed | MIT | Best-established token contract and block line maps; GFM is configurable rather than an all-or-nothing parser. |
| **Marko** | 2.2.4 (2026-08-12), Python `>=3.9` | CommonMark 0.31.2; `Markdown.parse()` returns an object AST; bundled `marko.ext.gfm` | Pure Python, zero mandatory dependencies | MIT | Strongest source-span model and bundled GFM AST, but source mapping first shipped in 2.2.4, only 17 days before this review. |
| **Mistune** | 3.3.4 (2026-07-22), Python `>=3.8` | Custom Markdown grammar; `create_markdown(renderer=None)` or `renderer="ast"` returns nested token dictionaries | Pure Python; no dependency on Python 3.11 (`typing-extensions` only below 3.11) | BSD-3-Clause | Small and fast with convenient AST output, but not CommonMark-conformant and its public AST has no source positions. |
| **Python-Markdown** | 3.10.3 (2026-07-30), Python `>=3.10` | John Gruber/Python-Markdown dialect; public API is Markdown-to-HTML, internally passing through `ElementTree` | Pure Python, zero mandatory dependencies | BSD-3-Clause | Maintained and extensible, but neither CommonMark/GFM nor a public source-preserving AST/token API. |

Additional exclusions:

- `commonmark.py` is explicitly described as **DEPRECATED** and its GitHub repository is archived; it is not a maintained candidate.
- GitHub's `cmark-gfm` is authoritative and robust GFM, but it is C99 rather than a pure-Python package and therefore conflicts with the requested implementation footprint.
- `mistletoe` is a maintained pure-Python CommonMark AST parser with native tables/strikethrough, but its documented lifecycle couples parsing to renderer setup and its public documentation does not provide source ranges. It offers no decisive advantage over the two conforming leaders above for this validator.

### Feature and API Comparison

#### markdown-it-py 4.2.0

**API shape and determinism**

```python
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

parser = MarkdownIt("commonmark", {"html": True}).enable("table")
tokens = parser.parse(source)
tree = SyntaxTreeNode(tokens)
```

The public token is a dataclass-like object with stable structural fields: `type`, `tag`, `nesting`, `attrs`, `map`, `children`, `content`, `markup`, `info`, `meta`, and `block`. `Token.as_dict()` is available for a JSON-compatible representation. Opening and closing block tokens form a flat stream; inline children sit under an `inline` token. `SyntaxTreeNode` collapses matching open/close tokens for tree traversal. Explicit construction of one parser configuration makes extension behavior repeatable.

**Required constructs**

- Tables: the GFM table rule is in core but disabled by the `commonmark` preset. `.enable("table")` enables it without adding a package. The 1.0 changelog states that table parsing was aligned to the GFM specification; 4.0 added a cap on auto-completed cells.
- Fenced code: core `fence` tokens expose full block content, fence marker through `markup`, info string through `info`, and block lines through `map`.
- HTML comments: with `html=True`, a standalone comment is an `html_block` token and an embedded comment is an `html_inline` child token; `content` preserves the raw comment. The official block rule explicitly recognizes `<!--` through `-->`. If HTML is disabled, comments are not available as HTML tokens, so the validator must choose this option deliberately.
- Links, headings, lists, paragraphs, and tables are distinct token kinds suitable for cardinality/order checks. The flat stream is especially convenient for validating ordered governed sections.

**Source positions**

`Token.map` is documented as `[line_begin, line_end]`: zero-based start and exclusive end lines for block tokens. It converts naturally to this repository's one-based inclusive convention as `(line_begin + 1, line_end)`. Inline child tokens generally have `map=None`; their containing block/`inline` token carries the line map. There are no public column or character offsets. Consequently, block diagnostics are directly grounded, while an inline link/comment diagnostic can reliably cite its enclosing block but not its exact column without a separate scanner.

**Extensions**

- Presets are explicit: `commonmark`, `zero`, `js-default`, `gfm-like`, and `gfm-like2`.
- `gfm-like` adds table, strikethrough, and linkify but requires optional `linkify-it-py`; `gfm-like2` adds task lists, alerts, and single-tilde strikethrough.
- For the stated template node set, `commonmark` plus only `table` avoids unrelated syntax and the optional linkifier. Rules can be individually enabled/disabled. Third-party syntax plugins are optional via `mdit-py-plugins` and should not be needed for the initial contract.

#### Marko 2.2.4

**API shape and constructs**

```python
from marko import Markdown
from marko.ext.gfm import GFM

document = Markdown(extensions=[GFM]).parse(source)
```

The result is an object tree rooted at `Document`, with classes such as `Heading`, `Paragraph`, `FencedCode`, `HTMLBlock`, and inline `Link`/`InlineHTML`. The bundled GFM extension contributes table/row/cell, task-list, strikethrough, autolink, and alert elements. Fenced code exposes `lang` and extra info separately. Comments are represented within `HTMLBlock.body` or `InlineHTML` content because both HTML token classes implement CommonMark raw HTML recognition.

**Source positions**

Version 2.2.4 added `source_span=(start, end)`, `start_pos`, `end_pos`, and inline `syntax_spans` to every AST element. These are exact character offsets into **normalized** source (`CRLF`/`CR` becomes `LF`), not original-byte offsets. GFM table code explicitly populates spans for tables, rows, and cells. This is materially richer than markdown-it-py's line maps and supports exact comment/link diagnostics, but consumers need tests around extension-created nodes and line-ending normalization because the feature is new.

**Extensions and state**

Extensions are ordered mixins/elements and order affects priority. The API documentation says `Markdown` instances are not thread-safe; create one per thread. The core has no mandatory dependency; optional TOC/code-highlighting/repr features add separate packages.

#### Mistune 3.3.4

```python
import mistune

parse = mistune.create_markdown(renderer=None, plugins=["table"])
tokens, state = parse.parse(source)
```

The AST is a list of nested dictionaries such as `{"type": "paragraph", "children": ...}`. Tables are a bundled plugin. Fenced blocks are core `block_code` tokens with `style="fenced"`, a `marker`, raw content, and optional `attrs.info`. Comments are core `block_html`/`inline_html` raw tokens. The public token examples and parser implementation do not attach line/column/offset spans; cursors are parser state, not retained AST contract. Table behavior also requires separate `table_in_quote` and `table_in_list` plugins in those container contexts. Mistune's own Marko comparison notes that Mistune does not comply with CommonMark, so deterministic output is possible only for Mistune's dialect, not a claimed CommonMark/GFM contract.

#### Python-Markdown 3.10.3

Its public `markdown.markdown()`/`Markdown.convert()` API returns HTML. The pipeline preprocesses source lines, builds an `ElementTree`, runs inline tree processors, serializes, then post-processes. Raw HTML/comments are moved through an HTML stash, which is useful for rendering but not a source-preserving comment AST. Fenced code and PHP Markdown Extra-style tables are bundled extensions, not a GFM parser. Extension loading can occur by installed entry-point string or import path, and extension order/state can change output. No public nodes carry source positions. These properties make it appropriate for rendering ecosystems but not for the task's deterministic source-grounded conformance inspection.

### Security Implications

Structural parsing and HTML rendering are different trust boundaries:

1. **Do not render submitted Markdown as part of validation.** Raw HTML, comments, links, and fenced code should remain inert token data. XSS sanitization is irrelevant to AST-only validation, but becomes mandatory if parser-generated HTML is ever displayed.
2. **HTML must be enabled for markdown-it-py comment detection.** The official security guide warns that its CommonMark default permits arbitrary HTML and is unsafe to render without sanitization. Enabling HTML is acceptable for inspection only; never interpret or execute token content.
3. **Keep the grammar fixed.** Do not dynamically load parser plugins or Python-Markdown entry points from user input. A fixed in-code parser construction prevents environment-dependent node sets and plugin code execution.
4. **Bound source size and nesting before parse.** Malicious Markdown can target regex, bracket, reference, table, or nesting complexity. markdown-it-py defaults `maxNesting` to 20 and has recent fixes for quadratic reference/text joining, table cell expansion, and earlier ReDoS; it is integrated with OSS-Fuzz. Marko 2.2.3/2.2.4 fixed an infinite loop and quadratic line-break case. These controls complement, rather than replace, the CLI's required input budget.
5. **URLs are data during validation.** markdown-it-py rejects several dangerous protocols during rendering, Mistune and Marko have renderer URL guards, and Python-Markdown explicitly does not sanitize output. Contract validation should inspect declared link shape/fields without treating any renderer's URL policy as a sanitizer.

### Packaging and Version Constraints

- All four shortlisted releases install on Python 3.11. Their default branches already advertise higher minimums in some cases (for example, current Python-Markdown `master` says `>=3.11`, while release 3.10.3 metadata says `>=3.10`), so released PyPI metadata—not an untagged branch—must define compatibility.
- markdown-it-py is the only recommended candidate adding a transitive runtime dependency: `mdurl~=0.1`. Tables do **not** require installing `[linkify]` or `[plugins]`.
- A bounded major requirement such as `markdown-it-py>=4.2,<5` matches the repository's existing dependency style and avoids silent adoption of a future token-contract break. The project changelog identifies prior major releases as containing internal/public parsing changes.
- Marko can be held as the fallback if exact source spans become a hard requirement: `marko>=2.2.4,<3` is the first range with documented element source maps.

## Recommendation

Use **markdown-it-py 4.2.x**, constructed explicitly as `MarkdownIt("commonmark", {"html": True}).enable("table")`, and inspect tokens rather than rendered HTML.

Why it is the best default for this CLI:

- It provides the most mature, documented, typed token stream for deterministic structural checks, current CommonMark 0.31.2 alignment, core GFM tables, raw comment visibility, and direct block line maps.
- It permits the exact grammar needed by the template contract without enabling linkification, task syntax, typographic rewriting, or third-party plugins.
- Its one small transitive dependency is a reasonable trade for stronger conformance history, strict typing, fuzzing, and security maintenance.
- Its line-level map is sufficient for the repository's one-based inclusive diagnostics for governed block nodes. Inline violations should cite the enclosing block line range; the absence of exact inline offsets must be made explicit in the validator contract.

Choose **Marko 2.2.4+** instead only if exact character spans for every inline node are an immediate non-negotiable requirement. It is technically compelling and dependency-free, but its source-map API is brand new and normalized-text-relative; that raises more adoption risk than markdown-it-py's established block-line maps for the first release.

## External References

### Primary sources

- [markdown-it-py usage and token stream](https://markdown-it-py.readthedocs.io/en/latest/using.html) — presets, rule enabling, plugins, token fields, and `SyntaxTreeNode`.
- [markdown-it-py Token API](https://markdown-it-py.readthedocs.io/en/latest/api/markdown_it.token.html) — exact `Token` fields and `[line_begin, line_end]` map definition.
- [markdown-it-py security guide](https://markdown-it-py.readthedocs.io/en/latest/security.html) — raw HTML defaults, sanitization boundary, URL restrictions, and plugin/DOM-clobbering warning.
- [markdown-it-py repository and changelog](https://github.com/executablebooks/markdown-it-py) — MIT license, CommonMark claims, maintenance, typing/fuzzing, releases, and dependency metadata.
- [markdown-it-py HTML block rule](https://github.com/executablebooks/markdown-it-py/blob/master/markdown_it/rules_block/html_block.py) — explicit HTML comment token recognition and line mapping.
- [Marko repository](https://github.com/frostming/marko) — CommonMark 0.31.2, GFM extension, dependencies, Python support, MIT license, and changelog.
- [Marko API reference](https://marko-py.readthedocs.io/en/latest/api.html) — object AST, parser API, thread-safety note, source spans, and syntax spans.
- [Marko GFM implementation](https://github.com/frostming/marko/tree/master/marko/ext/gfm) — table/row/cell AST and source-span population.
- [Mistune guide and API](https://mistune.lepture.com/en/latest/guide.html) — AST renderer, plugins, HTML escaping defaults, and parser customization.
- [Mistune repository](https://github.com/lepture/mistune) — release metadata, BSD license, runtime dependencies, and security reporting.
- [Python-Markdown library reference](https://python-markdown.github.io/reference/) — HTML-oriented public API, extension loading, parser lifecycle, thread safety, and sanitization warning.
- [Python-Markdown tables documentation](https://python-markdown.github.io/extensions/tables/) — PHP Markdown Extra table dialect and maintenance status.
- [GFM specification](https://github.github.com/gfm/) — normative definition of GFM as a strict CommonMark superset and its table/task/strikethrough/autolink extensions.
- [Archived commonmark.py repository metadata](https://api.github.com/repos/readthedocs/commonmark.py) — archived/deprecated status.
- [GitHub cmark-gfm repository](https://github.com/github/cmark-gfm) — official C implementation, GFM AST, fuzzing, and security behavior; excluded on pure-Python grounds.

### Related Specs

- No package-specific Trellis spec currently defines a Markdown parser contract. General validation guidance appears in `.trellis/spec/guides/cross-layer-thinking-guide.md:33-33` and `.trellis/spec/guides/cross-layer-thinking-guide.md:112-112`.

## Caveats / Not Found

- No shortlisted parser treats arbitrary malformed Markdown as a syntax error; CommonMark defines any character sequence as a document. Closed-template validation must therefore reject unexpected resulting nodes/content rather than expect parser exceptions.
- markdown-it-py source maps are block line ranges, not exact spans. Its inline `html_inline`/link children usually have no map.
- Marko source-span behavior was verified from current 2.2.4 documentation/source and changelog, but not yet through this repository's own cross-platform fixture suite.
- “GFM-like” does not imply GitHub.com's post-processing or sanitization. The CLI's contract should name the exact enabled grammar rather than claim complete GitHub rendering equivalence.
