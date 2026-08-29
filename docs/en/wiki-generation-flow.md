Below is the complete current `repo-dive` flow, from installing the Skill, building the index, planning the structure, retrieving Evidence page by page, and having the Agent generate the body, through to building the final `wiki.md`.

## Overview

```text
Install the wiki Skill
    ↓
Agent activates the wiki Skill
    ↓
Preflight the CLI, repository, and working tree
    ↓
repo-dive index
    ↓
Agent plans the Wiki structure
    ↓
repo-dive wiki structure
    ↓
Loop over each page:
    repo-dive wiki evidence
        ↓
    Agent generates Markdown from Evidence
        ↓
    repo-dive wiki page
    ↓
repo-dive wiki status
    ↓
repo-dive wiki build
    ↓
<repository>/.repo-dive/wiki.md
```

This flow has a clear boundary:

| Participant | Responsibility |
|---|---|
| `repo-dive` CLI | Scanning, parsing, indexing, retrieval, state management, citation validation, Evidence freshness, and Markdown assembly |
| Calling Agent | Planning the Wiki structure, using the current model to generate page bodies, selecting citations, and handling recovery |
| `wiki` Skill | Telling the Agent the order in which to call the CLI and the rules for each step |

The CLI does not invoke a generative model by itself.

---

# 1. Install the Wiki Skill

Run this in the target repository:

```bash
repo-dive init
```

An interactive TTY displays five platforms for multi-selection:

```text
1. Claude Code
2. OpenAI Codex CLI
3. OpenCode
4. Gemini CLI
5. GitHub Copilot
```

You can also install non-interactively:

```bash
repo-dive init . \
  --agent claude-code \
  --agent codex \
  --agent opencode \
  --agent gemini-cli \
  --agent github-copilot \
  --format json
```

Installation locations:

| Agent | Skill location |
|---|---|
| Claude Code | `.claude/skills/wiki` |
| Codex | `.agents/skills/wiki` |
| OpenCode | `.agents/skills/wiki` |
| Gemini CLI | `.agents/skills/wiki` |
| GitHub Copilot | `.agents/skills/wiki` |

The latter four platforms share one installation directory; four duplicate copies are not written.

This step only installs the Skill. It neither generates a Wiki nor builds an index.

---

# 2. Agent Activates the Skill

The user can trigger it with natural language:

```text
Generate a Chinese Wiki for the current repository.
```

The explicit invocation for each Agent can also be used:

| Agent | Common invocation |
|---|---|
| Claude Code | `/wiki` |
| Codex | `$wiki` or `/skills` |
| OpenCode | Load the `wiki` Skill |
| Gemini CLI | Activate the `wiki` Skill |
| GitHub Copilot | `/wiki` |

The Skill's core orchestration rules are in:

```text
skills/wiki/SKILL.md
```

Detailed input, recovery, and error contracts are in:

```text
skills/wiki/references/workflow-contract.md
```

---

# 3. Preflight Stage

The Agent performs preflight checks first instead of beginning generation immediately.

## 3.1 Determine the Repository

The current workspace root is used by default.

If the user supplies a URL, the Skill does not clone it automatically:

```text
https://github.com/example/project
```

Cloning requires the user's explicit authorization first.

## 3.2 Check the CLI

The Agent checks:

```bash
command -v repo-dive
repo-dive --version
repo-dive wiki --help
```

If the CLI is absent, the Agent stops and reports the installation prerequisite; it does not silently download software.

## 3.3 Check the Working Tree

```bash
git status --short
```

The purpose is to record and protect the user's existing changes. Generating a Wiki must not overwrite or revert user code.

## 3.4 Decide the Index Scope

The Agent considers excluding high-noise directories such as:

```text
node_modules/
.venv/
dist/
build/
generated/
vendor/
.repo-dive/
```

Whether tests should be excluded depends on the Wiki's goal. Test code should usually remain when the Wiki needs to explain actual behavior and validation.

See `skills/wiki/SKILL.md:21-32` for the preflight requirements.

---

# 4. Build the Repository Index

## 4.1 Command

```bash
repo-dive index <repository> \
  --exclude "node_modules/**" \
  --exclude ".venv/**" \
  --format json
```

The complete arguments include:

```bash
repo-dive index <repository> \
  [--include <glob>]... \
  [--exclude <glob>]... \
  [--max-file-size <bytes>] \
  [--max-chunk-lines <lines>] \
  [--embedding-model <local-model-directory>] \
  [--vector-failure strict|degraded] \
  --format json
```

Defaults:

| Parameter | Default |
|---|---:|
| `max-file-size` | 1,000,000 bytes |
| `max-chunk-lines` | 200 |
| Vector model | Disabled |

## 4.2 Indexing Process

```text
Scan repository files
    ↓
Read and classify files
    ↓
Python AST / Tree-sitter / text parsing
    ↓
Split into Chunks
    ↓
Extract Symbols and Relationships
    ↓
Build BM25 index
    ↓
Build structural relationship index
    ↓
Optionally build Vector index
    ↓
Write temporary SQLite database
    ↓
Integrity validation
    ↓
Atomically publish the current Index Generation
```

The index contains:

- File records
- Chunks
- Symbols
- Relationships such as Import, Call, Inheritance, and Contains
- BM25 postings and statistics
- Optional float32 Vectors

## 4.3 Index Files

```text
<repository>/.repo-dive/
├── index -> index-generations/<build-id>
└── index-generations/
    └── <build-id>/
        ├── index.sqlite3
        ├── manifest.json
        └── metadata.json
```

`.repo-dive/index` is a symbolic link to the current valid index generation.

A new index is built completely before the pointer is switched atomically. A failed build does not damage the old index.

## 4.4 Successful Result

The result looks approximately like this:

```json
{
  "schema_version": "1.0",
  "command": "index",
  "repository": "/absolute/project",
  "result": {
    "build_id": "abc123",
    "files": 120,
    "indexed_files": 115,
    "skipped_files": 5,
    "chunks": 850,
    "symbols": 430,
    "relationships": 970,
    "reused_files": 0,
    "rebuilt_files": 120
  },
  "warnings": []
}
```

The Agent must verify exit code `0` before continuing.

## 4.5 Index Freshness

Later Wiki commands rescan the repository and calculate its fingerprint using the original Include/Exclude arguments.

Writing `structure.json` or `page.json` into the repository after indexing can cause:

```text
index_stale
```

The Skill therefore requires these orchestration inputs to be placed in a temporary directory outside the repository.

---

# 5. Agent Plans the Wiki Structure

After indexing succeeds, the Agent plans the Wiki from repository documentation, directory structure, entry-point code, module boundaries, and user requirements.

The CLI neither decides the page count automatically nor imposes a fixed template.

The Agent must decide:

- Wiki title
- Wiki description
- Output language
- Sections
- Pages
- Stable Section IDs
- Stable Page IDs
- Page descriptions
- Files relevant to each page
- Relationships between pages

## 5.1 `structure.json`

```json
{
  "schema_version": "1.0",
  "title": "Repo Dive Project Wiki",
  "description": "Architecture and implementation documentation for developers.",
  "output_language": "zh-CN",
  "sections": [
    {
      "id": "foundations",
      "title": "Foundations",
      "pages": [
        {
          "id": "overview",
          "title": "Project Overview",
          "description": "Explain the project's goals, boundaries, core modules, and main workflows.",
          "relevant_files": [
            "README.md",
            "src/repo_dive/cli.py"
          ],
          "related_page_ids": [
            "architecture"
          ]
        },
        {
          "id": "architecture",
          "title": "System Architecture",
          "description": "Explain the dependencies among scanning, parsing, indexing, retrieval, Context, and Wiki.",
          "relevant_files": [
            "src/repo_dive/indexing/service.py",
            "src/repo_dive/retrieval/service.py",
            "src/repo_dive/wiki/service.py"
          ],
          "related_page_ids": [
            "overview"
          ]
        }
      ]
    }
  ]
}
```

## 5.2 Structure Validation

The CLI enforces that:

- `schema_version` is exactly `"1.0"`
- At least one Section exists
- Every Section contains at least one Page
- Section IDs are unique
- Page IDs are globally unique
- IDs, titles, and descriptions are non-empty
- `related_page_ids` point to pages in the current structure
- A page does not relate to itself
- `relevant_files` exist in the current index
- Paths are repository-relative POSIX paths
- Absolute paths are forbidden
- `..` is forbidden
- Backslashes are forbidden
- Unknown fields are forbidden

The CLI can verify that files exist, but it cannot determine whether the Agent selected the truly most relevant files.

---

# 6. Submit the Wiki Structure

## 6.1 Command

```bash
repo-dive wiki structure <repository> \
  --input /tmp/repo-dive-structure.json \
  --format json
```

`structure` currently accepts only a file path, not stdin.

## 6.2 First Submission Behavior

The first submission creates:

```text
<repository>/.repo-dive/wiki.json
<repository>/.repo-dive/metadata.json
```

Every page initially has the status:

```text
pending
```

Example successful result:

```json
{
  "schema_version": "1.0",
  "command": "wiki structure",
  "repository": "/absolute/project",
  "result": {
    "changed": true,
    "created_page_ids": [
      "overview",
      "architecture"
    ],
    "invalidated_page_ids": [],
    "preserved_page_ids": [],
    "section_count": 1,
    "page_count": 2,
    "wiki_schema_version": "1.0",
    "metadata_schema_version": "1.0",
    "index_schema_version": 4,
    "index_build_id": "abc123"
  },
  "warnings": []
}
```

## 6.3 Repeated Submission

An exactly identical structure returns:

```json
{
  "changed": false
}
```

No state is updated and no file is rewritten.

If only Section order or Page order changes, or a page moves to another Section, its state can be preserved as long as the page definition does not change.

The following changes invalidate a page and return it to `pending`:

- Title changes
- Description changes
- `relevant_files` changes
- `related_page_ids` changes
- Output language changes
- Evidence used by the page becomes stale

An output-language change invalidates every page.

---

# 7. Persistent Wiki State

## 7.1 Page States

```text
pending
evidence_ready
generated
failed
```

The state machine is:

```text
pending
  ├── evidence succeeds ───────────────→ evidence_ready
  └── evidence repository error ───────→ failed

evidence_ready
  ├── page succeeds ───────────────────→ generated
  ├── page content validation fails ───→ failed
  └── recollect Evidence ───────────────→ pending → evidence_ready

generated
  ├── recollect Evidence ───────────────→ pending → evidence_ready
  ├── structure changes or Evidence expires → pending
  └── repository error ────────────────→ failed

failed
  ├── recollect Evidence ───────────────→ pending → evidence_ready
  └── correct page submission ─────────→ pending → evidence_ready → generated
```

Allowed transitions are defined in `src/repo_dive/wiki/models.py:17-33`.

## 7.2 `wiki.json`

Page state is persisted as:

```json
{
  "id": "architecture",
  "title": "System Architecture",
  "description": "Explain the core modules and data flow.",
  "status": "pending",
  "relevant_files": [
    "src/repo_dive/wiki/service.py"
  ],
  "related_page_ids": [],
  "evidence": [],
  "evidence_snapshot": null,
  "citation_ids": [],
  "body": null,
  "error": null
}
```

This file is the core of the resumable workflow.

---

# 8. Get Current Status

The Agent normally runs this after submitting the structure or when resuming work:

```bash
repo-dive wiki status <repository> --format json
```

Example result:

```json
{
  "complete": false,
  "counts": {
    "pending": 2,
    "evidence_ready": 0,
    "generated": 0,
    "failed": 0
  },
  "sections": [
    {
      "id": "foundations",
      "title": "Foundations",
      "pages": [
        {
          "id": "architecture",
          "title": "System Architecture",
          "status": "pending",
          "next_action": "collect_evidence",
          "evidence_count": 0,
          "citation_count": 0,
          "has_body": false,
          "has_error": false
        }
      ]
    }
  ]
}
```

State-to-next-action mapping:

| State | `next_action` |
|---|---|
| `pending` | `collect_evidence` |
| `evidence_ready` | `generate_page` |
| `generated` | `complete` |
| `failed` | `retry` |

Important details:

- `status` is read-only.
- `status` does not rescan the repository.
- `status` does not check whether Evidence is still fresh.
- `complete: true` only means every page has status `generated`.
- `complete: true` does not prove that `wiki.md` has been built.

---

# 9. Collect Evidence for One Page

For a `pending` page, the Agent runs:

```bash
repo-dive wiki evidence <repository> \
  --page architecture \
  --token-budget 8000 \
  --max-results 40 \
  --format json
```

Argument constraints:

| Argument | Constraint |
|---|---|
| `--page` | Must be a Page ID in the current structure |
| `--token-budget` | Must be a positive integer |
| `--max-results` | 1 to 50; default 10 |
| `--format json` | Agent automation should pass this explicitly |

## 9.1 Query Construction

The CLI constructs a Query from the page definition:

```text
<page title>
<page description>
path:<relevant-file-1>
path:<relevant-file-2>
```

For example:

```text
System Architecture
Explain the module relationships among scanning, indexing, retrieval, and Wiki.
path:src/repo_dive/indexing/service.py
path:src/repo_dive/wiki/service.py
```

`path:` is currently only a retrieval hint, not a hard path filter. Results can therefore include other relevant files.

## 9.2 Actual Retrieval Channels

Currently, `wiki evidence` uses:

```text
BM25 keyword retrieval
+ structural symbol and relationship retrieval
+ Weighted RRF fusion
+ overlap deduplication
+ Token Budget packing
```

It currently does not use the vector channel, even when Vectors exist in the index.

Default fusion parameters:

| Parameter | Value |
|---|---:|
| Strategy | `weighted_rrf` |
| `rrf_k` | 60 |
| BM25 weight | 1.0 |
| Structural weight | 1.0 |
| Vector weight | 0.0 |
| Overlap threshold | 0.8 |

This differs from the general-purpose `search` and `context` commands. Those commands can use vector retrieval through `--embedding-model`, but `wiki evidence` currently has no such argument.

## 9.3 EvidencePacker

Candidate results enter the budget packer.

The Packer guarantees that it:

- Returns only complete Chunks
- Does not truncate source code in the middle
- Keeps total estimated Tokens within the budget
- By default prevents one file from occupying too many results
- Deduplicates overlapping Chunks
- Preserves paths and line numbers
- Generates stable Evidence IDs

Exclusion reasons include:

```text
duplicate
budget
low_score
```

If the budget is too small to fit even one complete Chunk, it returns:

```text
wiki_evidence_empty
```

The Agent must not invent citations when there is no Evidence.

## 9.4 Evidence Output

The result looks approximately like this:

```json
{
  "page_id": "architecture",
  "status": "evidence_ready",
  "query": "System Architecture\nExplain the core modules.\npath:src/repo_dive/wiki/service.py",
  "token_budget": 8000,
  "estimated_tokens": 3150,
  "reserved_tokens": 120,
  "truncated": false,
  "result_count": 8,
  "max_results": 40,
  "excluded": {
    "duplicate": 2,
    "budget": 0,
    "low_score": 3
  },
  "fusion": {
    "strategy": "weighted_rrf",
    "rrf_k": 60,
    "channel_weights": {
      "lexical": 1.0,
      "structural": 1.0
    },
    "overlap_threshold": 0.8
  },
  "repository_fingerprint": "...",
  "index_schema_version": 4,
  "index_build_id": "abc123",
  "generated_at": "...",
  "items": [
    {
      "evidence_id": "evidence:...",
      "chunk_id": "chunk:...",
      "content_hash": "...",
      "path": "src/repo_dive/wiki/service.py",
      "start_line": 263,
      "end_line": 363,
      "estimated_tokens": 850,
      "text": "Complete source Chunk...",
      "symbol": {
        "id": "symbol:...",
        "kind": "method",
        "name": "collect_evidence",
        "qualified_name": "WikiService.collect_evidence"
      },
      "lexical_score": 2.14,
      "structural_score": 1.0,
      "vector_score": null,
      "fused_score": 0.0325,
      "reasons": []
    }
  ]
}
```

## 9.5 Evidence Persistence

The CLI does not merely emit Evidence to stdout; it also writes citations and a Snapshot to `wiki.json`:

```json
{
  "status": "evidence_ready",
  "evidence": [
    {
      "evidence_id": "evidence:...",
      "chunk_id": "chunk:...",
      "path": "src/repo_dive/wiki/service.py",
      "start_line": 263,
      "end_line": 363,
      "content_hash": "..."
    }
  ],
  "evidence_snapshot": {
    "query": "...",
    "repository_fingerprint": "...",
    "index_schema_version": 4,
    "index_build_id": "abc123",
    "token_budget": 8000,
    "estimated_tokens": 3150,
    "reserved_tokens": 120,
    "truncated": false,
    "retrieval": {
      "max_results": 40,
      "strategy": "weighted_rrf",
      "rrf_k": 60,
      "channel_weights": {
        "lexical": 1.0,
        "structural": 1.0
      },
      "overlap_threshold": 0.8
    },
    "generated_at": "..."
  }
}
```

The general-purpose `repo-dive context` therefore cannot replace `wiki evidence`. General Context does not create a persistent page-level Snapshot.

---

# 10. Agent Generates the Body from Evidence

This is the boundary between the CLI and the generative model.

The CLI has completed:

```text
Scanning
Indexing
Retrieval
Fusion
Deduplication
Budgeted selection
Evidence persistence
```

The Agent then uses the current model to generate page Markdown from `items`.

The Agent should:

- Use only the Evidence returned for the current page.
- Not use Evidence IDs from another page.
- Not construct Evidence IDs itself.
- Not repeat the page title.
- Explain design intent and trade-offs instead of merely restating syntax.
- Support diagrams with Evidence.
- Select only Evidence that truly supports the body as citations.

The CLI can verify that citations are valid, but it cannot verify that every sentence in the body is actually supported by Evidence.

For example, if the Agent writes a hallucinated body while attaching valid Evidence IDs, the CLI cannot make a semantic factual judgment.

---

# 11. Construct the Page Submission

The Agent generates:

```json
{
  "schema_version": "1.0",
  "page_id": "architecture",
  "body": "The system separates scanning, parsing, indexing, and Wiki assembly into independent stages...\n",
  "evidence_ids": [
    "evidence:abc...",
    "evidence:def..."
  ]
}
```

Exactly four fields are strictly required:

```text
schema_version
page_id
body
evidence_ids
```

Body constraints:

- It must not be empty after trimming whitespace
- It must be UTF-8 encodable
- It must not contain NUL
- Maximum 200,000 UTF-8 bytes
- It should not repeat the Page Heading

Evidence ID constraints:

- The list must not be empty
- IDs must be unique
- IDs must come from the page's current Snapshot
- IDs must not have leading or trailing whitespace
- IDs must still identify Chunks in the current index

---

# 12. Submit One Page

## 12.1 File Input

```bash
repo-dive wiki page <repository> \
  --page architecture \
  --input /tmp/architecture-page.json \
  --format json
```

## 12.2 stdin Input

```bash
repo-dive wiki page <repository> \
  --page architecture \
  --input - \
  --format json < /tmp/architecture-page.json
```

## 12.3 CLI Validation Order

The CLI checks:

1. Whether the Wiki is initialized.
2. Whether `--page` exists.
3. Whether the JSON `page_id` matches `--page`.
4. Whether the page state permits submission.
5. Whether the page has a complete Evidence Snapshot.
6. Whether the Evidence remains fresh.
7. Whether the body is valid.
8. Whether `evidence_ids` belong to the current page.
9. Whether the page has already been generated.

Submitting a page directly while it is `pending` returns:

```text
wiki_page_state_invalid
```

The page must first enter:

```text
evidence_ready
```

## 12.4 Idempotency of a Generated Page

If the page is already `generated`, resubmitting exactly the same body and Evidence IDs returns:

```json
{
  "changed": false
}
```

The file is not rewritten.

If the body or Evidence IDs differ, the CLI refuses to overwrite it:

```text
wiki_page_state_invalid
```

To regenerate it, first rerun:

```bash
repo-dive wiki evidence ...
```

This moves the page back through:

```text
generated → pending → evidence_ready
```

## 12.5 Successful Output

```json
{
  "page_id": "architecture",
  "status": "generated",
  "changed": true,
  "body_bytes": 5240,
  "citation_count": 4,
  "evidence_ids": [
    "evidence:abc...",
    "evidence:def..."
  ]
}
```

The successful result does not echo the body.

---

# 13. Sequentially Loop Over All Pages

For every Page, the Agent performs:

```text
wiki evidence
    ↓
Agent generates Markdown
    ↓
wiki page
```

Pseudocode:

```text
for page in structure.pages:
    if page.status == pending:
        evidence = repo-dive wiki evidence(page)
        body = current_agent_model.generate(evidence.items)
        repo-dive wiki page(page, body, evidence_ids)

    if page.status == evidence_ready:
        body = current_agent_model.generate(saved_evidence)
        repo-dive wiki page(page, body, evidence_ids)

    if page.status == generated:
        skip

    if page.status == failed:
        recover based on error
```

These write operations must not run concurrently because every one updates the shared:

```text
.repo-dive/wiki.json
.repo-dive/metadata.json
```

The current Skill explicitly requires sequential execution; see `skills/wiki/SKILL.md:49-60`.

---

# 14. Evidence Freshness Validation

Page submission and Build both revalidate Evidence.

Any of the following changes makes Evidence stale:

- The Chunk no longer exists
- Chunk ID mismatch
- Chunk content hash changes
- File path changes
- Start line changes
- End line changes
- Evidence Snapshot is missing
- Index Schema version changes

The validation logic is in `src/repo_dive/wiki/validation.py:33-72`.

Importantly, freshness is not a simple Build ID comparison.

After reindexing, Evidence can remain valid if its:

```text
Chunk ID
content hash
path
line range
```

are still exactly the same.

---

# 15. Check All Page States

```bash
repo-dive wiki status <repository> --format json
```

Target result:

```json
{
  "complete": true,
  "counts": {
    "pending": 0,
    "evidence_ready": 0,
    "generated": 8,
    "failed": 0
  }
}
```

This means all page bodies have been submitted, but it does not mean the final `wiki.md` has been built.

---

# 16. Build the Final Wiki

## 16.1 Command

```bash
repo-dive wiki build <repository> --format json
```

## 16.2 Enforced Preconditions

Build requires:

- Every page has status `generated`
- Every page has a body
- Every page has at least one Citation
- The current index is valid
- All Evidence is fresh
- The index does not switch during Build

If any page is not generated:

```json
{
  "error": {
    "code": "wiki_build_incomplete",
    "details": {
      "page_ids": [
        "architecture",
        "retrieval"
      ]
    }
  }
}
```

If Evidence is stale:

```json
{
  "error": {
    "code": "wiki_evidence_stale",
    "details": {
      "page_ids": [
        "retrieval"
      ]
    }
  }
}
```

A failed Build does not overwrite the old `wiki.md`.

## 16.3 Assembled Markdown Content

The final document contains, in structure order:

```text
# Wiki Title

Wiki Description

## Contents

Section/Page table of contents

## Section

### Page

Agent-generated body

#### Related pages

#### Sources
```

Sources are converted into relative links with line numbers:

```markdown
- [src/repo_dive/wiki/service.py:263-363](../src/repo_dive/wiki/service.py#L263-L363)
```

Section and Page Anchors use the SHA-256 of stable IDs:

```text
section-<sha256(section-id)>
page-<sha256(page-id)>
```

Reordering pages therefore does not change their Anchors.

## 16.4 Build Output

```json
{
  "artifact_path": ".repo-dive/wiki.md",
  "bytes": 48210,
  "changed": true,
  "page_count": 8,
  "section_count": 3,
  "source_count": 34,
  "sha256": "..."
}
```

Final file:

```text
<repository>/.repo-dive/wiki.md
```

Repeating the same Build returns:

```json
{
  "changed": false,
  "sha256": "same as last time"
}
```

---

# 17. Final Artifact Layout

The complete `.repo-dive/` layout is approximately:

```text
.repo-dive/
├── index -> index-generations/<build-id>
├── index-generations/
│   └── <build-id>/
│       ├── index.sqlite3
│       ├── manifest.json
│       └── metadata.json
├── wiki.json
├── metadata.json
└── wiki.md
```

Responsibilities of each file:

| File | Responsibility |
|---|---|
| `index.sqlite3` | Chunks, Symbols, relationships, BM25, and optional Vectors |
| Index `manifest.json` | Index arguments, file identities, Build ID, and repository fingerprint |
| Index `metadata.json` | Current index-generation metadata |
| Root `wiki.json` | Wiki structure, page state, Evidence, bodies, and citations |
| Root `metadata.json` | Identity binding among the Wiki, repository, and index |
| `wiki.md` | Final stable published document |

---

# 18. Interruption Recovery Flow

When resuming, always run this first:

```bash
repo-dive wiki status <repository> --format json
```

Recovery matrix:

| Page state | Action |
|---|---|
| `pending` | Run `wiki evidence`, generate the body, then run `wiki page` |
| `evidence_ready` | Generate the body from the current Evidence, then run `wiki page` |
| `generated` | Do nothing |
| `failed` | Fix the error according to its type, then rerun Evidence or Page |

If the previous `wiki evidence` stdout was lost while the page has status `evidence_ready`, the safest course is to rerun Evidence and obtain a new complete text response.

## Common Recovery Errors

| Error code | Recovery |
|---|---|
| `index_not_found` | Run `repo-dive index` |
| `index_stale` | Reindex with the same Include/Exclude arguments |
| `wiki_not_initialized` | Submit the Wiki Structure |
| `wiki_evidence_empty` | Increase the budget or improve the page description |
| `wiki_evidence_missing` | Rerun `wiki evidence` |
| `wiki_evidence_stale` | Regenerate only the listed pages |
| `wiki_build_incomplete` | Generate the listed incomplete pages |
| `wiki_page_state_invalid` | Perform the correct next step for the current state |
| `index_changed_during_operation` | Retry after the index is stable |
| `wiki_state_incomplete` | Diagnose the missing `wiki.json` or Metadata; the CLI does not repair it automatically |

Exit codes:

| Exit code | Meaning |
|---:|---|
| `0` | Success |
| `2` | Command or input validation error |
| `3` | Repository, index, Evidence, or Wiki state error |
| `4` | Internal operation failure |

Exit code `2` must not be retried unchanged; the input must be corrected first.

---

# 19. Atomicity and Idempotency

| Operation | Behavior |
|---|---|
| `index` | Atomically switches the current pointer after the new Generation is completely built |
| `wiki structure` | An identical structure returns `changed: false` |
| `wiki evidence` | Every success creates a new Snapshot; it is not write-free idempotent |
| `wiki page` | Repeating the same page submission returns `changed: false` |
| `wiki page` | A Generated page cannot be overwritten directly with a different body |
| `wiki status` | Read-only |
| `wiki build` | Identical Markdown returns `changed: false` |
| JSON writes | Per-file temporary write, `fsync`, and `os.replace` |
| Markdown writes | Atomically replace only after all validation succeeds |

Note that `wiki.json` and root-level `metadata.json` are each atomic files, but there is no cross-file database transaction between them.

If one write succeeds and the other fails, later reads detect:

```text
wiki_state_incomplete
```

The CLI does not guess how to repair it.

---

# 20. What the State Machine Guarantees and What Depends on the Agent

## Enforced by the CLI

- Legal page-state transitions
- Valid structure fields
- Unique Page IDs
- Relevant Files exist
- Evidence IDs belong to the current page
- Evidence is fresh
- A page cannot skip Evidence and generate directly
- A Generated page cannot be overwritten directly
- Every page must be complete before Build
- Every page must have a body and citations
- A failed Build does not damage the old `wiki.md`
- Final document order and Anchors are deterministic

## Responsibilities of the Agent and Skill

- Whether the Wiki structure is reasonable
- Whether the page count is appropriate
- Whether page descriptions retrieve the right code
- Whether Evidence is used carefully
- Whether the body is genuinely factually accurate
- Whether design intent is explained
- Whether diagrams are useful
- Whether page write operations run sequentially
- Whether exit codes and recovery are handled correctly
- Whether index exclusions and Evidence limitations are reported

In summary:

```text
CLI owns the verifiable deterministic boundary
+
Skill orchestrates the workflow
+
Agent plans and generates
=
Complete Wiki generation system
```
