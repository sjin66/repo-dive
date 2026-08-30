# CLI Contract

## Audience

This contract targets non-interactive callers such as GitHub Copilot, shell scripts, and CI. Human-friendly output is secondary to predictable process behavior.

## Invocation

Commands accept the repository path explicitly. They must not infer a different repository from an unrelated parent directory. Relative input paths are resolved against the current working directory and reported back as normalized absolute repository roots in metadata.

Functional commands support:

```text
repo-dive <command> [repository] --format json
```

The current build implements `index`, `search`, `context`, `wiki classify`, `wiki init`, `wiki evidence`, `wiki page`, `wiki validate`, `wiki build`, and `wiki status`; deprecated `wiki structure` remains for compatibility.

## RAG Command Boundary

Command families expose each RAG stage independently:

- `index`: scan, parse, chunk, and build structural/BM25/optional-vector indexes.
- `search`: retrieve ranked evidence and preserve per-channel scores.
- `context`: deduplicate and package evidence under a caller-supplied token budget.
- `wiki`: persist agent-generated page state and assemble `.repo-dive/wiki.md`.

`index`, `search`, and `context` are deterministic RAG operations. `wiki classify`, `wiki init`, `wiki evidence`, `wiki page`, `wiki validate`, `wiki build`, and `wiki status` provide the complete governed, persistent, resumable offline Wiki workflow. None implicitly calls a generative model.

The context command requires a positive token budget and accepts a bounded retrieval-candidate count:

```text
repo-dive context <repository> <query> --token-budget N [--max-results COUNT] --format json|markdown
```

Its JSON result reports `token_budget`, `estimated_tokens`, `reserved_tokens`, `estimator`, `truncated`, fixed `duplicate`/`budget`/`low_score` exclusion counts, fusion parameters, and complete Evidence items. Each item includes a stable `evidence_id`, repository-relative path, inclusive line range, symbol metadata when available, source text, scores, and retrieval reasons.

### Explicit vector enhancement

`index`, `search`, and `context` accept the same optional vector controls:

```text
--embedding-model <existing-local-directory>
--vector-failure strict|degraded
```

Without `--embedding-model`, commands do not construct an embedding provider,
import Sentence Transformers, add Vector result metadata, or change the
two-channel BM25/structural output contract. With the option, `index` stores the
provider/model/dimensions identity and embeds only new or changed Chunks when
the identity still matches. A changed identity re-embeds every Chunk.

`strict` is the default: provider setup, model mismatch, embedding, or Vector
index errors fail the command and preserve the previous published index.
`degraded` continues with BM25 and structural retrieval and emits a safe
`vector_degraded:<error-code>` warning. Vector result metadata reports status,
failure policy, opaque identity, indexed/embedded/reused Chunk counts, query
embedding count, and safe error code. Search hits always retain
`lexical_score`, `structural_score`, `vector_score`, and `fused_score`; a score
is `null` when that channel did not retrieve the Chunk.

The governed Wiki commands are:

```text
repo-dive wiki classify <repository> [--template ID] --format json|markdown
repo-dive wiki init <repository> [--template ID] --locale en|zh-CN|ja --format json|markdown
repo-dive wiki evidence <repository> --page <page-id> --token-budget N [--max-results COUNT] --format json|markdown
repo-dive wiki page <repository> --page <page-id> --input <page.json|-> --format json|markdown
repo-dive wiki validate <repository> --format json|markdown
repo-dive wiki build <repository> --format json|markdown
repo-dive wiki status <repository> --format json|markdown
```

`wiki classify` is read-only. `wiki init` deterministically classifies the current published index and composes the exact localized built-in Section/Page/Subsection structure. Callers control only exact locale and an optional registered primary-template override; they cannot submit governed nodes, ordering, source paths, or documentation-only flags. Classification and template identities are persisted in Metadata and returned by init/status.

Status output reports ordered sections and pages, state counts, whether a body or error exists, and one next action per page without returning generated bodies. The mappings are `pending -> collect_evidence`, `evidence_ready -> generate_page`, `generated -> complete`, and `failed -> retry`.

`wiki evidence` derives its query deterministically from the persisted Page and Subsection titles, descriptions, and direct-source paths. It reserves one complete Chunk for every required direct path before filling the remaining budget with bounded hybrid retrieval results, then writes the Page Evidence snapshot before emitting source text. A successful Page enters `evidence_ready`; insufficient direct-Evidence budget does not mutate state, while other empty-bundle or repository/index retrieval failures mark only the requested Page `failed` with a safe error code.

The persisted snapshot records the query, repository fingerprint, index Schema/build identity, token accounting, estimator, truncation flag, retrieval/fusion parameters, generation timestamp, and included Evidence references. Every reference stores the Chunk ID, content hash, path, and inclusive line range. Build identity is audit metadata; freshness is checked against the current index Schema and each referenced Chunk identity/hash, so an unrelated index rebuild does not invalidate unaffected pages. Stale Evidence is rejected by the page/build validation boundary.

`wiki page` accepts a bounded UTF-8 JSON file or `--input -` for stdin. Governed submission Schema `2.0` accepts exactly `schema_version`, `page_id`, and one ordered `subsections` entry per persisted Subsection. Each entry has `subsection_id`, Markdown `body`, and non-empty unique `evidence_ids`; non-documentation Subsections must cite covering direct Evidence. The selected and submitted Page IDs and exact Subsection order must match, cited IDs must belong to the current Evidence snapshot, H1-H4 and raw HTML are rejected, and all bodies together are limited to 200,000 UTF-8 bytes. The outer input is bounded at 1,500,000 bytes so escaped JSON cannot create an unbounded read.

A valid `evidence_ready` page becomes `generated`. A `failed` page with a still-valid Evidence snapshot may be corrected and submitted without touching other pages. Repeating the exact generated body and citation list is a no-write success; attempting to replace a generated page through this command is rejected. Results and diagnostics report only sizes, counts, IDs, status, and safe error codes—they do not echo the submitted body or repository source.

`wiki build` requires every page to be `generated` with a body and at least one current citation. It validates all page Evidence against one current published-index view and verifies that build identity again immediately before writing. Incomplete pages return `wiki_build_incomplete`; stale pages return `wiki_evidence_stale`; a concurrent index publication returns `index_changed_during_operation`. These failures preserve any existing `.repo-dive/wiki.md`, and page-related errors include only ordered Page IDs.

The assembled document preserves Section/Page/Subsection order and contains localized scope/version disclosure, three-level Contents, explicit stable anchors, CLI-owned H2/H3/H4 headings, caller H5/H6 content, related-page links, and source links with inclusive line ranges. Section/Page anchors hash their persisted IDs; Subsection anchors hash the Page ID, a NUL separator, and the Subsection ID. Source targets are URL-encoded paths relative to `.repo-dive/wiki.md`. The CLI rejects raw HTML and stores accepted Markdown as data; consumers that render HTML must still use a trusted Markdown renderer and an appropriate HTML sanitization policy.

JSON output reports `artifact_path`, UTF-8 `bytes`, `changed`, Section/Page/source counts, and `sha256` without returning the assembled body. Markdown output writes the exact assembled document to stdout, while both formats first obey the same atomic artifact write. Rebuilding identical state is a no-write success with `changed: false`.

## Agent Invocation Examples

No MCP server is required. A calling agent should execute the CLI directly and
use this order for a persistent Wiki:

```text
index -> wiki classify -> wiki init -> wiki evidence (Context) -> caller generates prose -> wiki page -> wiki validate -> wiki build
```

Run `wiki status` between resumable steps. Generic `context` is appropriate for
ad hoc answers; `wiki evidence` must be used for Wiki pages because it persists
the Evidence snapshot validated by `wiki page` and `wiki build`.

### Index success

<!-- contract-example:index-success -->

```bash
repo-dive index /workspace/project --format json
```

```json
{
  "schema_version": "1.0",
  "command": "index",
  "repository": "/workspace/project",
  "result": {
    "build_id": "0123456789abcdef0123456789abcdef",
    "chunks": 24,
    "deleted_files": 0,
    "files": 8,
    "index_schema_version": 4,
    "indexed_files": 8,
    "manifest_schema_version": "2.0",
    "rebuilt_files": 8,
    "relationships": 11,
    "repository_fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "reused_files": 0,
    "skipped_files": 0,
    "symbols": 17,
    "warning_count": 0
  },
  "warnings": []
}
```

### Search success

<!-- contract-example:search-success -->

```bash
repo-dive search /workspace/project "build_parser" --max-results 10 --format json
```

```json
{
  "schema_version": "1.0",
  "command": "search",
  "repository": "/workspace/project",
  "result": {
    "fusion": {
      "channel_weights": {
        "lexical": 1.0,
        "structural": 1.0
      },
      "overlap_threshold": 0.8,
      "rrf_k": 60,
      "strategy": "weighted_rrf"
    },
    "hits": [
      {
        "chunk_id": "chunk:example",
        "end_line": 25,
        "fused_score": 0.03278688524590164,
        "lexical_score": 1.25,
        "path": "src/repo_dive/cli.py",
        "reasons": [
          "lexical_match:build",
          "lexical_match:parser",
          "rrf:lexical:rank=1,weight=1.000000,contribution=0.016393442623",
          "symbol_match:name_exact:repo_dive.cli.build_parser",
          "rrf:structural:rank=1,weight=1.000000,contribution=0.016393442623"
        ],
        "start_line": 12,
        "structural_score": 0.95,
        "symbol": {
          "id": "symbol:example",
          "kind": "function",
          "name": "build_parser",
          "qualified_name": "repo_dive.cli.build_parser"
        },
        "text": "def build_parser():\n    ...\n",
        "vector_score": null
      }
    ],
    "max_results": 10,
    "query": "build_parser",
    "result_count": 1
  },
  "warnings": []
}
```

### Context success

<!-- contract-example:context-success -->

```bash
repo-dive context /workspace/project "build_parser" --token-budget 1200 --max-results 10 --format json
```

```json
{
  "schema_version": "1.0",
  "command": "context",
  "repository": "/workspace/project",
  "result": {
    "estimated_tokens": 184,
    "estimator": "conservative_utf8_bytes_v1",
    "excluded": {
      "budget": 0,
      "duplicate": 0,
      "low_score": 0
    },
    "fusion": {
      "channel_weights": {
        "lexical": 1.0,
        "structural": 1.0
      },
      "overlap_threshold": 0.8,
      "rrf_k": 60,
      "strategy": "weighted_rrf"
    },
    "items": [
      {
        "chunk_id": "chunk:example",
        "end_line": 25,
        "estimated_tokens": 116,
        "evidence_id": "evidence:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "fused_score": 0.03278688524590164,
        "lexical_score": 1.25,
        "path": "src/repo_dive/cli.py",
        "reasons": [
          "lexical_match:build",
          "lexical_match:parser",
          "rrf:lexical:rank=1,weight=1.000000,contribution=0.016393442623",
          "symbol_match:name_exact:repo_dive.cli.build_parser",
          "rrf:structural:rank=1,weight=1.000000,contribution=0.016393442623"
        ],
        "start_line": 12,
        "structural_score": 0.95,
        "symbol": {
          "id": "symbol:example",
          "kind": "function",
          "name": "build_parser",
          "qualified_name": "repo_dive.cli.build_parser"
        },
        "text": "def build_parser():\n    ...\n",
        "vector_score": null
      }
    ],
    "max_results": 10,
    "query": "build_parser",
    "reserved_tokens": 68,
    "result_count": 1,
    "token_budget": 1200,
    "truncated": false
  },
  "warnings": []
}
```

The calling model may now generate an answer, but must retain the returned
path and inclusive lines as its citation.

### Wiki file input and success

<!-- contract-example:wiki-success -->

`structure.json`:

```json
{
  "schema_version": "1.0",
  "title": "Project Wiki",
  "description": "Grounded repository documentation.",
  "output_language": "en",
  "sections": [
    {
      "id": "guide",
      "title": "Guide",
      "pages": [
        {
          "id": "overview",
          "title": "Overview",
          "description": "Explain the CLI entrypoint.",
          "relevant_files": [
            "src/repo_dive/cli.py"
          ],
          "related_page_ids": []
        }
      ]
    }
  ]
}
```

```bash
repo-dive wiki structure /workspace/project --input structure.json --format json
repo-dive wiki evidence /workspace/project --page overview --token-budget 1200 --max-results 10 --format json
```

The caller generates only the `body`; the CLI owns the page heading. It copies
the exact IDs returned by `wiki evidence` into `page.json`:

```json
{
  "schema_version": "1.0",
  "page_id": "overview",
  "body": "The CLI entrypoint builds a bounded argument parser and dispatches a typed command handler.\n",
  "evidence_ids": [
    "evidence:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  ]
}
```

```bash
repo-dive wiki page /workspace/project --page overview --input page.json --format json
```

```json
{
  "schema_version": "1.0",
  "command": "wiki page",
  "repository": "/workspace/project",
  "result": {
    "body_bytes": 92,
    "changed": true,
    "citation_count": 1,
    "evidence_ids": [
      "evidence:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    ],
    "page_id": "overview",
    "status": "generated"
  },
  "warnings": []
}
```

```bash
repo-dive wiki build /workspace/project --format json
```

```json
{
  "schema_version": "1.0",
  "command": "wiki build",
  "repository": "/workspace/project",
  "result": {
    "artifact_path": ".repo-dive/wiki.md",
    "bytes": 512,
    "changed": true,
    "page_count": 1,
    "section_count": 1,
    "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "source_count": 1
  },
  "warnings": []
}
```

### stdin and Markdown output

<!-- contract-example:stdin -->

File and stdin input use the same Page Submission Schema:

```bash
repo-dive wiki page /workspace/project --page overview --input page.json --format json
repo-dive wiki page /workspace/project --page overview --input - --format json < page.json
repo-dive search /workspace/project "build_parser" --max-results 10 --format markdown
```

Representative Markdown stdout begins with:

```markdown
# Repository search

- Query: "build_parser"
- Results: 1
- Fusion: weighted_rrf
```

### Error and recovery

<!-- contract-example:error -->

Commands in JSON mode emit a complete error document even when they fail:

```json
{
  "schema_version": "1.0",
  "command": "context",
  "error": {
    "code": "index_stale",
    "message": "Repository index is stale; run `repo-dive index` first.",
    "details": {
      "build_id": "0123456789abcdef0123456789abcdef"
    }
  }
}
```

<!-- contract-example:recovery -->

Use the process exit code before interpreting the envelope:

```text
0 -> consume result
2 -> correct arguments or JSON input; do not retry unchanged
3 + index_not_found/index_stale -> run index, then retry retrieval
3 + wiki_evidence_stale -> run wiki evidence again, regenerate, then submit wiki page
4 -> surface the safe diagnostic and preserve the last valid .repo-dive artifacts
```

After an interrupted Wiki run, call `repo-dive wiki status ... --format json`
and follow each page's `next_action`. Never treat stderr or an old generic
`context` response as persisted Wiki Evidence.

## Standard Streams

### JSON mode

- `stdout` contains exactly one UTF-8 JSON document.
- The document ends with one newline.
- Progress, warnings, and diagnostics go to `stderr`.
- ANSI escape sequences are disabled.
- Partial JSON is never written. Build the complete result before emitting it.

### Markdown mode

Commands that explicitly return Markdown may write raw UTF-8 Markdown to `stdout`. Diagnostics still go to `stderr`.

## Result Envelope

JSON commands use this top-level shape:

```json
{
  "schema_version": "1.0",
  "command": "context",
  "repository": "/absolute/path/to/repository",
  "result": {},
  "warnings": []
}
```

Errors written in JSON mode use a complete error envelope on `stdout` and human diagnostics on `stderr`:

```json
{
  "schema_version": "1.0",
  "command": "context",
  "error": {
    "code": "repository_not_found",
    "message": "Repository path does not exist."
  }
}
```

Error codes are stable machine identifiers; messages may improve without a schema-version change.

## Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Command completed successfully. |
| `2` | Invocation, option, or input-schema validation failed. |
| `3` | The repository or requested repository data is unavailable. |
| `4` | An internal operation failed after valid invocation. |

Signals and platform-level failures may use conventional shell codes outside this table.

## Evidence Locations

Paths are repository-relative POSIX strings, even on Windows. Line numbers are one-based and inclusive:

```json
{
  "path": "src/repo_dive/cli.py",
  "start_line": 12,
  "end_line": 25,
  "symbol": "build_parser"
}
```

A result without a trustworthy line range omits both line fields rather than guessing.

## Budgets

Commands that can return repository content accept explicit limits such as `--token-budget` or `--max-results`. The response reports the applied budget, estimated usage, and whether evidence was truncated. Context accounting reserves stable envelope and item metadata before admitting complete source bodies; it never trims an Evidence line range to fit.

## Idempotency and Writes

Read commands have no repository side effects. Index and wiki commands may write only beneath `<repository>/.repo-dive/`. Re-running a command with identical repository state and arguments produces equivalent structured output, excluding timestamps and duration fields.

Writes use temporary sibling files and atomic replacement. A failed command must not expose a half-written JSON or Markdown artifact.

## Compatibility

Adding optional fields is backward compatible. Renaming/removing fields, changing types, changing exit-code meaning, or changing artifact paths requires a schema or command version change.
