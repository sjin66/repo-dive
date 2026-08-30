# Wiki Workflow

## Purpose and Ownership

The Wiki workflow converts indexed local repository Evidence into one stable Markdown artifact without giving the CLI a language-model session. `repo-dive` owns structure validation, retrieval, Evidence snapshots, page state, citation validation, and atomic assembly. The calling agent owns page planning and prose generation with its current model.

An up-to-date index is a precondition:

```bash
repo-dive index <repository> --format json
```

The governed generation path is `init -> evidence -> page -> build -> status`. Schema 2.0 preserves an ordered `Section -> Page -> Subsection` outline. `status` is also safe at every checkpoint and is the normal resume entrypoint.

The deprecated manual flow was `structure -> evidence -> page -> build -> status`;
use explicit governed `init` for new state.

<!-- contract-section:commands -->
## Command Sequence

```bash
repo-dive wiki classify <repository> --format json
repo-dive wiki init <repository> --locale en --format json
repo-dive wiki status <repository> --format json
repo-dive wiki evidence <repository> --page <page-id> --token-budget 1200 --max-results 10 --format json
repo-dive wiki page <repository> --page <page-id> --input page.json --format json
repo-dive wiki page <repository> --page <page-id> --input - --format json < page.json
repo-dive wiki validate <repository> --format json
repo-dive wiki build <repository> --format json
repo-dive wiki status <repository> --format json
```

Use these smoke commands to verify the installed command surface without modifying a repository:

```bash
repo-dive wiki init --help
repo-dive wiki classify --help
repo-dive wiki evidence --help
repo-dive wiki page --help
repo-dive wiki validate --help
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

- `.repo-dive/wiki.json` is strict Schema `2.0` Wiki structure, Subsection contracts, Evidence roles, and Page state.
- `.repo-dive/metadata.json` is strict Schema `2.0` Wiki/repository/index identity, including Git commit and dirty state copied from the published index.
- `.repo-dive/wiki.md` is created or replaced only by a successful `wiki build`.
- `.repo-dive/index` is the validated current index pointer. Callers may read documented metadata but must not mutate index internals.

`wiki.json` and the root Wiki metadata must either both exist or both be absent. If only one exists, commands return `wiki_state_incomplete`; they do not guess or repair the missing half. Invalid JSON, unknown/missing fields, and unsupported versions remain byte-for-byte available for diagnosis.

## 1. Classify and Initialize

`wiki classify` reads only the validated published index and returns the deterministic primary, topology, facets, matched signals, and index identity. `--template <registered-primary-id>` changes only the effective primary and records the override.

`wiki init` repeats that classification, composes the exact built-in template for the requested `en`, `zh-CN`, or `ja` locale, and persists the resulting ordered Section, Page, and Subsection contracts. The caller cannot submit IDs, order, titles, descriptions, direct paths, or `documentation_only` flags. Repeating the same init against the same index and locale is a no-write operation. Its result includes the complete classification and template identities together with structure counts.

`wiki structure --input structure.json` remains a deprecated compatibility command; it is not the governed initialization path.

## 2. Collect and Persist Evidence

`wiki evidence` derives its query from the persisted Page and Subsection titles, descriptions, and source paths. It reserves one complete, query-relevant Chunk from every required direct path before packing supplemental lexical/structural candidates.

Candidates are fused with `weighted_rrf`, overlap-deduplicated, and passed through `EvidencePacker`. Only complete Chunks that fit `token_budget` are returned. The CLI first atomically persists the Evidence references and snapshot, then emits the full Evidence text to stdout. A successful page moves to `evidence_ready`.

Each persisted Evidence reference contains:

- `evidence_id`, `chunk_id`, `content_hash`;
- repository-relative POSIX `path`;
- one-based inclusive `start_line` and `end_line`;
- `role` (`direct` or `supplemental`) plus direct-path/Subsection coverage.

The page-level `evidence_snapshot` contains `query`, `repository_fingerprint`, `index_schema_version`, `index_build_id`, `token_budget`, `estimated_tokens`, `reserved_tokens`, `estimator`, `truncated`, `generated_at`, and retrieval parameters (`max_results`, `strategy`, `rrf_k`, `channel_weights`, `overlap_threshold`).

If mandatory direct Evidence cannot fit, `wiki_evidence_direct_budget_insufficient` reports the required minimum without mutating Page state. Other repository-state collection errors use the established safe failed transition. Invalid CLI options fail before collection and do not mutate Page state.

## 3. Generate and Submit One Page

The calling model receives the Evidence result and writes one fragment for every exact Subsection ID in contract order. Each non-documentation Subsection cites direct Evidence that covers it. The CLI owns H1-H4; fragments may use H5/H6 only and cannot contain raw HTML. The CLI does not generate or rewrite this prose.

```json
{
  "schema_version": "2.0",
  "page_id": "overview",
  "subsections": [{
    "subsection_id": "runtime_flow",
    "body": "##### Call chain\n\nThe entrypoint delegates startup.\n",
    "evidence_ids": ["evidence:<sha256>"]
  }]
}
```

The submission is strict: the ordered Subsection array must exactly match the persisted contract. Bodies must be non-empty UTF-8 Markdown within the Page byte limit. Evidence IDs must be unique within each fragment, belong to that Page, and still match the current index by Chunk ID, hash, path, and line range.

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

The deterministic Markdown contains localized scope/version disclosure, three-level Contents, ordered H2 Sections/H3 Pages/H4 Subsections, H4 related/source blocks, caller H5/H6 content, and source links. The disclosure binds scan policy, counts, index build/fingerprint, source commit and dirty/non-Git state, and generation timestamp to the validated published index.

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

If Evidence collection sets a page to `failed`, successful recovery clears its safe `error` field. Governed page-submission validation errors do not mutate Page state. Old bodies or Evidence references may remain in persisted state for diagnosis, but consumers must follow `status`/`next_action` and must not treat them as current output.

## Failure Guarantees

- `index_not_found` and `index_stale`: run `repo-dive index`, then resume the affected Wiki stage.
- `wiki_not_initialized`: run `wiki init` after indexing.
- `wiki_build_incomplete`: generate only the listed pages.
- `wiki_evidence_stale`: recollect and regenerate only the listed pages.
- `wiki_evidence_direct_budget_insufficient`: increase the explicit budget; Page state was not mutated.
- `wiki_page_state_invalid`: follow the current page state; generated content cannot be overwritten directly.
- `wiki_state_invalid`, `wiki_metadata_invalid`, or unsupported versions: preserve the bytes for diagnosis; commands do not repair them.
- Atomic write or assembly failure never truncates the previous public JSON or Markdown artifact.
