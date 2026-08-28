# CLI Contract

## Audience

This contract targets non-interactive callers such as GitHub Copilot, shell scripts, and CI. Human-friendly output is secondary to predictable process behavior.

## Invocation

Commands accept the repository path explicitly. They must not infer a different repository from an unrelated parent directory. Relative input paths are resolved against the current working directory and reported back as normalized absolute repository roots in metadata.

Functional commands support:

```text
repo-dive <command> [repository] --format json
```

The current build implements `index`, `search`, `context`, `wiki structure`, `wiki evidence`, `wiki page`, `wiki build`, and `wiki status` in addition to `--help` and `--version`.

## RAG Command Boundary

Command families expose each RAG stage independently:

- `index`: scan, parse, chunk, and build structural/BM25/optional-vector indexes.
- `search`: retrieve ranked evidence and preserve per-channel scores.
- `context`: deduplicate and package evidence under a caller-supplied token budget.
- `wiki`: persist agent-generated page state and assemble `.repo-dive/wiki.md`.

`index`, `search`, and `context` are deterministic RAG operations. `wiki structure`, `wiki evidence`, `wiki page`, `wiki build`, and `wiki status` provide the complete persistent, resumable offline Wiki workflow. None of these commands implicitly calls a generative model.

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

The structure command reads a bounded UTF-8 JSON document from an explicit file:

```text
repo-dive wiki structure <repository> --input structure.json --format json|markdown
repo-dive wiki evidence <repository> --page <page-id> --token-budget N [--max-results COUNT] --format json|markdown
repo-dive wiki page <repository> --page <page-id> --input <page.json|-> --format json|markdown
repo-dive wiki build <repository> --format json|markdown
repo-dive wiki status <repository> --format json|markdown
```

Structure input Schema `1.0` accepts only `schema_version`, `title`, `description`, `output_language`, and ordered `sections`. A section contains only `id`, `title`, and ordered `pages`; a page contains only `id`, `title`, `description`, `relevant_files`, and `related_page_ids`. IDs must be unique, relationships must resolve to submitted page IDs, and relevant files must exist in the current published index. Lifecycle fields such as status, evidence, body, and error cannot be injected through this command.

Reapplying an identical structure is byte-idempotent. New pages start as `pending`; changing a page title, description, relevant files, or relationships resets only that page to `pending` while preserving its previous evidence/body/error for diagnosis. Reordering or moving an otherwise unchanged page preserves its state. A repository/index identity or output-language change invalidates all retained pages.

Status output reports ordered sections and pages, state counts, whether a body or error exists, and one next action per page without returning generated bodies. The mappings are `pending -> collect_evidence`, `evidence_ready -> generate_page`, `generated -> complete`, and `failed -> retry`.

`wiki evidence` derives its query deterministically from the persisted page title, description, and `path:<relevant-file>` hints. It applies the same bounded hybrid retrieval and complete-Chunk context packing as `context`, but writes the page Evidence snapshot before emitting source text. A successful page enters `evidence_ready`; an empty bundle or repository/index retrieval failure marks only the requested page `failed` with a safe error code.

The persisted snapshot records the query, repository fingerprint, index Schema/build identity, token accounting, estimator, truncation flag, retrieval/fusion parameters, generation timestamp, and included Evidence references. Every reference stores the Chunk ID, content hash, path, and inclusive line range. Build identity is audit metadata; freshness is checked against the current index Schema and each referenced Chunk identity/hash, so an unrelated index rebuild does not invalidate unaffected pages. Stale Evidence is rejected by the page/build validation boundary.

`wiki page` accepts a bounded UTF-8 JSON file or `--input -` for stdin. Submission Schema `1.0` accepts exactly `schema_version`, `page_id`, Markdown `body`, and a non-empty unique `evidence_ids` array. The selected and submitted Page IDs must match; every cited ID must belong to that page's current Evidence snapshot; the snapshot must still match the published index; and the body is limited to 200,000 UTF-8 bytes. The outer input is bounded at 1,500,000 bytes so escaped JSON cannot create an unbounded read.

A valid `evidence_ready` page becomes `generated`. A `failed` page with a still-valid Evidence snapshot may be corrected and submitted without touching other pages. Repeating the exact generated body and citation list is a no-write success; attempting to replace a generated page through this command is rejected. Results and diagnostics report only sizes, counts, IDs, status, and safe error codes—they do not echo the submitted body or repository source.

`wiki build` requires every page to be `generated` with a body and at least one current citation. It validates all page Evidence against one current published-index view and verifies that build identity again immediately before writing. Incomplete pages return `wiki_build_incomplete`; stale pages return `wiki_evidence_stale`; a concurrent index publication returns `index_changed_during_operation`. These failures preserve any existing `.repo-dive/wiki.md`, and page-related errors include only ordered Page IDs.

The assembled document preserves Section/Page order and contains the Wiki title and description, a table of contents, explicit stable anchors, page headings, caller-generated bodies, related-page links, and source links with inclusive line ranges. Anchors are the `section-` or `page-` prefix plus the full SHA-256 of the persisted ID. Source targets are URL-encoded paths relative to `.repo-dive/wiki.md`. Callers should submit page body content without repeating the CLI-owned page heading. The CLI stores Markdown as data and does not execute or HTML-sanitize page bodies; consumers that render HTML must use a trusted Markdown renderer and an appropriate HTML sanitization policy.

JSON output reports `artifact_path`, UTF-8 `bytes`, `changed`, Section/Page/source counts, and `sha256` without returning the assembled body. Markdown output writes the exact assembled document to stdout, while both formats first obey the same atomic artifact write. Rebuilding identical state is a no-write success with `changed: false`.

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
