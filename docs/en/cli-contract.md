# CLI Contract

## Audience

This contract targets non-interactive callers such as GitHub Copilot, shell scripts, and CI. Human-friendly output is secondary to predictable process behavior.

## Invocation

Commands accept the repository path explicitly. They must not infer a different repository from an unrelated parent directory. Relative input paths are resolved against the current working directory and reported back as normalized absolute repository roots in metadata.

Functional commands will support:

```text
repo-dive <command> [repository] --format json
```

The foundation currently implements only `repo-dive --help` and `repo-dive --version`.

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

Future JSON commands use this top-level shape:

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

Commands that can return repository content accept explicit limits such as `--token-budget` or `--max-results`. The response reports the applied budget, estimated usage, and whether evidence was truncated. Stable metadata must not consume the caller's evidence budget.

## Idempotency and Writes

Read commands have no repository side effects. Index and wiki commands may write only beneath `<repository>/.repo-dive/`. Re-running a command with identical repository state and arguments produces equivalent structured output, excluding timestamps and duration fields.

Writes use temporary sibling files and atomic replacement. A failed command must not expose a half-written JSON or Markdown artifact.

## Compatibility

Adding optional fields is backward compatible. Renaming/removing fields, changing types, changing exit-code meaning, or changing artifact paths requires a schema or command version change.

