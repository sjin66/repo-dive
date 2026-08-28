# CLI Contract

## Audience

This contract targets non-interactive callers such as GitHub Copilot, shell scripts, and CI. Human-friendly output is secondary to predictable process behavior.

## Invocation

Commands accept the repository path explicitly. They must not infer a different repository from an unrelated parent directory. Relative input paths are resolved against the current working directory and reported back as normalized absolute repository roots in metadata.

Functional commands support:

```text
repo-dive <command> [repository] --format json
```

The current build implements `index`, `search`, `context`, `wiki structure`, and `wiki status` in addition to `--help` and `--version`.

## RAG Command Boundary

Command families expose each RAG stage independently:

- `index`: scan, parse, chunk, and build structural/BM25/optional-vector indexes.
- `search`: retrieve ranked evidence and preserve per-channel scores.
- `context`: deduplicate and package evidence under a caller-supplied token budget.
- `wiki`: persist agent-generated page state and assemble `.repo-dive/wiki.md`.

`index`, `search`, and `context` are available deterministic RAG operations. `wiki structure` and `wiki status` provide the first persistent Wiki boundary; evidence binding, page submission, and final assembly remain planned. None of these commands implicitly calls a generative model.

The context command requires a positive token budget and accepts a bounded retrieval-candidate count:

```text
repo-dive context <repository> <query> --token-budget N [--max-results COUNT] --format json|markdown
```

Its JSON result reports `token_budget`, `estimated_tokens`, `reserved_tokens`, `estimator`, `truncated`, fixed `duplicate`/`budget`/`low_score` exclusion counts, fusion parameters, and complete Evidence items. Each item includes a stable `evidence_id`, repository-relative path, inclusive line range, symbol metadata when available, source text, scores, and retrieval reasons.

The structure command reads a bounded UTF-8 JSON document from an explicit file:

```text
repo-dive wiki structure <repository> --input structure.json --format json|markdown
repo-dive wiki status <repository> --format json|markdown
```

Structure input Schema `1.0` accepts only `schema_version`, `title`, `description`, `output_language`, and ordered `sections`. A section contains only `id`, `title`, and ordered `pages`; a page contains only `id`, `title`, `description`, `relevant_files`, and `related_page_ids`. IDs must be unique, relationships must resolve to submitted page IDs, and relevant files must exist in the current published index. Lifecycle fields such as status, evidence, body, and error cannot be injected through this command.

Reapplying an identical structure is byte-idempotent. New pages start as `pending`; changing a page title, description, relevant files, or relationships resets only that page to `pending` while preserving its previous evidence/body/error for diagnosis. Reordering or moving an otherwise unchanged page preserves its state. A repository/index identity or output-language change invalidates all retained pages.

Status output reports ordered sections and pages, state counts, whether a body or error exists, and one next action per page without returning generated bodies. The mappings are `pending -> collect_evidence`, `evidence_ready -> generate_page`, `generated -> complete`, and `failed -> retry`.

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
