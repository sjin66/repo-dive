# Wiki Workflow

## Purpose

The wiki workflow turns local repository evidence into one stable Markdown document without requiring the CLI to own a language-model session. The calling agent orchestrates interpretation; `repo-dive` owns deterministic state, evidence, validation, and assembly.

## Artifact Layout

```text
<repository>/.repo-dive/
├── wiki.md
├── wiki.json
├── metadata.json
└── index/
```

- `wiki.md`: atomically assembled current document.
- `wiki.json`: versioned wiki structure, page states, relevant files, evidence references, and generated page bodies.
- `metadata.json`: repository identity, source commit, output language, timestamps, schema version, and index version.
- `index/`: implementation-private lexical, vector, and relationship data.

Only `wiki.md`, `wiki.json`, and `metadata.json` are public artifact contracts. Callers must not depend on files inside `index/`.

### Public JSON state

`wiki.json` uses its own `schema_version` and stores `title`, `description`, and ordered `sections`. Each section has a stable `id`, `title`, and ordered `pages`. Every page records:

- stable `id`, `title`, and `description`;
- `status`, `relevant_files`, and `related_page_ids`;
- complete `evidence` references with `evidence_id`, `chunk_id`, repository-relative POSIX `path`, and an inclusive line range;
- nullable generated `body` and safe `error` summary.

`metadata.json` has an independently evolvable `schema_version`. It records the normalized repository identity and fingerprint, optional source Commit, output language, timestamps, `wiki_schema_version`, `index_schema_version`, and `index_build_id`.

Readers reject unsupported artifact Schema versions and documents with missing required fields or unknown fields. Invalid or corrupt JSON is left byte-for-byte unchanged for diagnosis. Each public JSON file is serialized completely and replaced atomically; a failed replacement preserves that file's previous bytes.

## Stage 1: Repository Inventory

The CLI validates the repository root, applies include/exclude rules, scans supported files, reads project-level documentation, and records a deterministic inventory. Hidden generated directories and `.repo-dive/` itself are excluded.

Inventory results include paths, sizes, detected languages, content fingerprints, and source commit when available. Binary and unreadable files are reported as skipped evidence rather than silently treated as empty text.

## Stage 2: RAG Index Construction

The CLI parses supported source files, creates symbol-aligned chunks, and builds the local RAG indexes:

- a structural index for files, symbols, imports, calls, inheritance, and containment;
- a BM25 lexical index for identifiers, exact strings, configuration, and domain terms;
- an optional vector index for semantic recall when an embedding provider is explicitly configured.

Each indexed chunk keeps its repository-relative path, line range, symbol metadata, content fingerprint, and relationships. BM25 plus structural retrieval form the offline baseline; vector retrieval is an optional enhancement rather than a prerequisite.

## Stage 3: Wiki Structure

The calling agent receives the inventory and proposes a versioned structure containing:

- wiki title and description;
- ordered sections and pages;
- page identifiers that remain stable across regeneration;
- page descriptions and relationships;
- initial relevant-file candidates.

The CLI validates references and persists the accepted structure to `wiki.json`. It does not invent missing pages or silently repair unknown file paths.

The available command boundary is:

```text
repo-dive wiki structure <repository> --input structure.json --format json|markdown
repo-dive wiki status <repository> --format json|markdown
```

Structure submission is stateless: callers provide only titles, descriptions, output language, ordered section/page IDs, page relationships, and relevant-file hints. Persisted lifecycle fields are owned by the CLI. Reapplying the same structure performs no write. A changed page is reset to `pending`; unaffected stable Page IDs preserve their evidence and generated state, including when reordered or moved between sections.

## Stage 4: RAG Page Evidence

For each page, the agent requests evidence using the page topic and relevant-file hints. The RAG retrieval pipeline queries structural, BM25, and optional vector channels; fuses their candidates; removes duplicate or overlapping chunks; optionally expands symbol relationships; and applies an explicit context budget.

Every evidence item records its repository-relative path, line range when trustworthy, symbol when known, score components, and content fingerprint. Evidence is stored with the page state before prose generation starts.

## Stage 5: Augmented Generation and Persistence

The calling agent uses its current model and the returned evidence to write one Markdown page. The page is returned to the CLI through stdin or a structured input file. The CLI validates page identity, evidence citations, encoding, and size before persisting it.

Page generation is independently retryable. Completing one page must not require regenerating other completed pages.

This is the generation step of RAG. It runs in the calling Copilot session rather than inside the CLI, so it can reuse the caller's selected model and conversation while the evidence remains a versioned, inspectable CLI result.

## Stage 6: Assembly

When all required pages are ready, the CLI assembles:

1. document title and generation metadata;
2. table of contents;
3. ordered page anchors and headings;
4. related-page links;
5. page bodies and source references.

Assembly writes a temporary sibling file, verifies it, and atomically replaces `.repo-dive/wiki.md`. The previous document remains intact if validation or replacement fails.

## State Model

The workflow uses explicit states:

```text
uninitialized -> inventoried -> indexed -> structured -> retrieving -> generating -> complete
                                  |           |             |             |
                                  +-----------+-------------+-> failed <--+
```

Page states are `pending`, `evidence_ready`, `generated`, or `failed`. Retrying a failed page does not reset successful pages. A source fingerprint change marks affected evidence and pages stale without deleting their previous content.

`wiki status` exposes these states without returning generated bodies. Its next actions are `collect_evidence`, `generate_page`, `complete`, and `retry`, respectively, so a non-interactive caller can resume work deterministically.

Valid page transitions are explicit:

- `pending -> evidence_ready | failed`;
- `evidence_ready -> generated | failed | pending`;
- `generated -> failed | pending`;
- `failed -> pending`.

Returning to `pending` represents retry or invalidation and may preserve the previous body for diagnosis until a later command replaces it. All self-transitions and skipped lifecycle steps are rejected.

## Regeneration

Regeneration compares repository fingerprints with metadata. Unchanged inventories and indexes are reused. Changed files invalidate their chunks and dependent page evidence. Stable page identifiers allow callers to update only affected content and then rebuild the single Markdown artifact.

## Failure Semantics

- Invalid repository input fails before artifacts are created.
- Index failure leaves the previous valid index and wiki untouched.
- Invalid agent-provided structure or page content is rejected with structured diagnostics.
- Partial generation remains resumable in `wiki.json`.
- Assembly failure never truncates the previous `wiki.md`.
