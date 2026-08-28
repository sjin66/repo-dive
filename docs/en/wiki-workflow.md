# Wiki Workflow

## Purpose and Ownership

The Wiki workflow converts indexed local repository Evidence into one stable Markdown artifact without giving the CLI a language-model session. `repo-dive` owns structure validation, retrieval, Evidence snapshots, page state, citation validation, and atomic assembly. The calling agent owns page planning and prose generation with its current model.

An up-to-date index is a precondition:

```bash
repo-dive index <repository> --format json
```

The complete generation path is `structure -> evidence -> page -> build -> status`. `status` is also safe at every checkpoint and is the normal resume entrypoint.

<!-- contract-section:commands -->
## Command Sequence

```bash
repo-dive wiki structure <repository> --input structure.json --format json
repo-dive wiki status <repository> --format json
repo-dive wiki evidence <repository> --page <page-id> --token-budget 1200 --max-results 10 --format json
repo-dive wiki page <repository> --page <page-id> --input page.json --format json
repo-dive wiki page <repository> --page <page-id> --input - --format json < page.json
repo-dive wiki build <repository> --format json
repo-dive wiki status <repository> --format json
```

Use these smoke commands to verify the installed command surface without modifying a repository:

```bash
repo-dive wiki structure --help
repo-dive wiki evidence --help
repo-dive wiki page --help
repo-dive wiki build --help
repo-dive wiki status --help
```

For each page, repeat `evidence -> calling-model generation -> page`. Run `build` only after every page is `generated`, then use `status` for the final persisted summary. A `complete: true` status means all pages are generated; it does not prove that `wiki.md` has already been built, because build state is not stored separately.

## Artifact Layout

```text
<repository>/.repo-dive/
├── index -> index-generations/<build-id>
├── index-generations/<build-id>/
│   ├── index.sqlite3
│   ├── manifest.json
│   └── metadata.json
├── wiki.json
├── metadata.json
└── wiki.md
```

- `.repo-dive/wiki.json` is strict Schema `1.0` Wiki structure and page state.
- `.repo-dive/metadata.json` is strict Schema `1.0` Wiki/repository/index identity. It is distinct from generation-local index metadata.
- `.repo-dive/wiki.md` is created or replaced only by a successful `wiki build`.
- `.repo-dive/index` is the validated current index pointer. Callers may read documented metadata but must not mutate index internals.

`wiki.json` and the root Wiki metadata must either both exist or both be absent. If only one exists, commands return `wiki_state_incomplete`; they do not guess or repair the missing half. Invalid JSON, unknown/missing fields, and unsupported versions remain byte-for-byte available for diagnosis.

## 1. Submit Structure

The caller submits a stateless structure proposal. Lifecycle fields are intentionally absent:

```json
{
  "schema_version": "1.0",
  "title": "Repository Wiki",
  "description": "Grounded local repository documentation.",
  "output_language": "en",
  "sections": [
    {
      "id": "guide",
      "title": "Guide",
      "pages": [
        {
          "id": "overview",
          "title": "Overview",
          "description": "Explain the application entrypoint.",
          "relevant_files": ["src/app.py"],
          "related_page_ids": []
        }
      ]
    }
  ]
}
```

Section and Page IDs must be unique and non-empty. `related_page_ids` must reference pages in the same proposed Wiki. `relevant_files` must be repository-relative POSIX paths present in the current index. Unknown fields, unknown paths, absolute paths, `..`, and backslashes are rejected.

On first submission, every page becomes `pending`. Reapplying an identical structure is a no-write operation. Stable pages whose title, description, relevant files, relationships, and output language remain unchanged preserve their state even when reordered or moved between sections. New pages are created; changed pages, stale pages, and every page after an output-language change are invalidated to `pending`.

The result reports `changed`, `created_page_ids`, `invalidated_page_ids`, `preserved_page_ids`, Schema versions, counts, and index build identity.

## 2. Collect and Persist Evidence

`wiki evidence` derives its query from the persisted page title, description, and `path:<relevant-file>` hints. The current command uses the lexical BM25 and structural channels only; unlike `search` and `context`, it does not accept or inject an Embedding Provider. Vector indexing therefore does not change this command's current ranking path.

Candidates are fused with `weighted_rrf`, overlap-deduplicated, and passed through `EvidencePacker`. Only complete Chunks that fit `token_budget` are returned. The CLI first atomically persists the Evidence references and snapshot, then emits the full Evidence text to stdout. A successful page moves to `evidence_ready`.

Each persisted Evidence reference contains:

- `evidence_id`, `chunk_id`, `content_hash`;
- repository-relative POSIX `path`;
- one-based inclusive `start_line` and `end_line`.

The page-level `evidence_snapshot` contains `query`, `repository_fingerprint`, `index_schema_version`, `index_build_id`, `token_budget`, `estimated_tokens`, `reserved_tokens`, `estimator`, `truncated`, `generated_at`, and retrieval parameters (`max_results`, `strategy`, `rrf_k`, `channel_weights`, `overlap_threshold`).

If a repository-state error occurs during collection, the page becomes `failed` and stores only the safe error code. Invalid CLI options fail before collection and do not mutate page state.

## 3. Generate and Submit One Page

The calling model receives the Evidence result and writes page-body Markdown. It must cite a non-empty subset of the exact returned `evidence_id` values. The CLI does not generate or rewrite this prose.

```json
{
  "schema_version": "1.0",
  "page_id": "overview",
  "body": "The entrypoint delegates application startup.\n",
  "evidence_ids": ["evidence:<sha256>"]
}
```

The submission is strict: exactly `schema_version`, `page_id`, `body`, and `evidence_ids` are accepted. The body must be non-empty UTF-8 Markdown within the CLI byte limit. Evidence IDs must be unique, non-empty, belong to that page, and still match the current index by Chunk ID, hash, path, and line range.

A valid submission stores body plus `citation_ids` and moves the page to `generated`. The success result reports only body byte count and citation metadata, not the body. Repeating the identical generated submission is a no-write operation; a different submission to an already generated page is rejected. Explicit regeneration starts by running `wiki evidence` again, which clears old citations and returns the page to `evidence_ready` with a new snapshot.

The assembled document owns the Page heading. The caller should provide body content without repeating that heading.

<!-- contract-section:page-state -->
## Page State Machine and Status

There is no separately persisted repository-level state machine. The durable lifecycle is per page:

```text
pending -> evidence_ready
pending -> failed
evidence_ready -> generated
evidence_ready -> failed
evidence_ready -> pending
generated -> failed
generated -> pending
failed -> pending
```

Self-transitions and skipped model transitions are rejected. Service operations may compose valid transitions atomically; for example, resubmitting corrected content from `failed` with still-current Evidence passes through `pending` and `evidence_ready` before persisting `generated`.

`wiki status` is read-only and does not return generated bodies or the saved error code. It reports Wiki/index Schema identities, counts for all four states, `complete`, and for every page: `status`, `next_action`, `evidence_count`, `citation_count`, `has_body`, and `has_error`.

```text
pending        -> collect_evidence
evidence_ready -> generate_page
generated      -> complete
failed         -> retry
```

Status reflects persisted state; it does not rescan the repository or validate Evidence freshness. Freshness is enforced by `wiki evidence`, `wiki page`, and `wiki build`.

## 4. Build Markdown

`wiki build` requires every page to be `generated`, have a body, and have at least one citation. It then validates every cited Evidence reference against the current published index and checks that the index did not change during assembly.

The deterministic Markdown contains the Wiki title/description, a table of contents, ordered Section and Page headings, related-page links, caller-generated bodies, and source links. Section/Page anchors are a type prefix plus the full SHA-256 of the stable ID. Source links are relative to `.repo-dive/wiki.md` and include `#Lx` or `#Lx-Ly` fragments.

Only after all checks pass does the store atomically replace `.repo-dive/wiki.md`. Failure preserves the previous Markdown. Rebuilding identical state returns `changed: false`; `--format markdown` returns exactly the persisted document, while JSON returns path, byte count, SHA-256, section/page/source counts, and `changed`.

<!-- contract-section:single-page-recovery -->
## Single-Page Recovery

Start every resume with:

```bash
repo-dive wiki status <repository> --format json
```

Then recover only the affected page:

1. For `pending`, run `wiki evidence`, generate from the returned Evidence, then submit with `wiki page`.
2. For `evidence_ready`, generate and submit directly from the saved/current Evidence response.
3. For `failed`, inspect the error returned by the failed command or the public page `error` in `.repo-dive/wiki.json`:
   - if page validation failed but its Evidence is still current, correct `page.json` and resubmit directly;
   - for missing/stale Evidence or an Evidence collection failure, fix/rebuild the index when required and rerun `wiki evidence` before generation.
4. Leave unrelated `generated` pages untouched.
5. When every page is generated, run `wiki build`, then `wiki status`.

After source changes, first run `repo-dive index`. A subsequent build can return `wiki_evidence_stale` with only the affected `page_ids`; the previous `.repo-dive/wiki.md` remains valid and unchanged. Recollect and regenerate those pages only. Merely seeing `generated` in `wiki status` is not a freshness guarantee.

If Evidence collection or page validation sets a page to `failed`, successful recovery clears its safe `error` field. Old bodies or Evidence references may remain in persisted state for diagnosis, but consumers must follow `status`/`next_action` and must not treat them as current output.

## Failure Guarantees

- `index_not_found` and `index_stale`: run `repo-dive index`, then resume the affected Wiki stage.
- `wiki_not_initialized`: submit a valid structure after indexing.
- `wiki_build_incomplete`: generate only the listed pages.
- `wiki_evidence_stale`: recollect and regenerate only the listed pages.
- `wiki_page_state_invalid`: follow the current page state; generated content cannot be overwritten directly.
- `wiki_state_invalid`, `wiki_metadata_invalid`, or unsupported versions: preserve the bytes for diagnosis; commands do not repair them.
- Atomic write or assembly failure never truncates the previous public JSON or Markdown artifact.
