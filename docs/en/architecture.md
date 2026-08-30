# Architecture

## System Boundary

`repo-dive` is a local, non-interactive process invoked by a human or coding agent. It reads one explicitly selected repository, writes repository-owned artifacts under `.repo-dive/`, and emits one complete JSON or Markdown result on stdout. The calling agent owns language-model generation; the CLI never starts a nested model session.

```text
calling agent
    | argv / stdin
    v
CLI commands
    |-- scan -> parse -> index
    |-- retrieve -> fuse -> pack context
    `-- persist Wiki state -> assemble Markdown
    v
stdout JSON/Markdown + <repository>/.repo-dive/
```

The implementation is local-first. The default lexical and structural paths require neither credentials nor network access. Vector support is opt-in and the implemented provider accepts only an existing local Sentence Transformers model directory.

## Design Principles

- **Deterministic core, probabilistic caller:** scanning, parsing, indexing, retrieval, validation, and assembly are reproducible from repository bytes and explicit options; interpretation and prose generation remain in the calling model.
- **Evidence before narrative:** context and Wiki commands preserve repository-relative POSIX paths, one-based inclusive line ranges, Chunk identities, hashes, and explainable scores.
- **Bounded work:** file size, Chunk line count, result count, graph traversal, embedding batch size, and context tokens all have explicit limits.
- **Resumable artifacts:** an index is published as a complete generation; Wiki pages have independent persisted states; identical submissions and builds are no-write operations.
- **Stable process contracts:** JSON Schema versions, exit codes, stdout/stderr separation, and public artifact paths are integration boundaries. Prompt wording is not an API.

<!-- contract-section:packages -->
## Package and Dependency Boundaries

These are implemented package boundaries, not a future plan:

```text
src/repo_dive/
├── cli.py                 process boundary and error/result serialization
├── commands/              index, search, context, map, and wiki adapters
├── scanner/               deterministic candidate discovery and file reads
├── parsing/               Chunk, Symbol, Relationship extraction
├── indexing/              SQLite store, BM25, graph, vectors, generations
├── providers/             optional local embedding provider selection
├── retrieval/             lexical, structural, vector, and weighted fusion
├── context/               token estimation and complete-Evidence packing
├── knowledge_map/         deterministic maps, views, Evidence, and enrichment
├── wiki/                  state, freshness, page submission, assembly
├── storage/               repository path validation and atomic writes
├── evaluation/            offline retrieval and context evaluation runner
├── errors.py              stable error categories and exit semantics
└── schema.py              versioned JSON result envelopes
```

The concrete dependency direction is:

```text
cli -> commands
commands -> indexing / retrieval / context / knowledge_map / wiki
scanner -> storage
parsing -> scanner
indexing -> scanner / parsing / providers / storage
retrieval -> indexing / parsing / providers
context -> retrieval / parsing
knowledge_map -> indexing / retrieval / context / storage
wiki -> indexing / retrieval / context / storage
evaluation -> indexing / retrieval / context
```

Lower-level domain models do not import command or CLI modules. Replaceable runtime boundaries are narrow Protocols where the implementation needs substitution: `SourceParser`, `EmbeddingProvider`, `StructuralGraph`, and `TokenEstimator`. Filesystem and SQLite persistence are concrete local adapters, not hypothetical remote abstractions.

## Scan and Parse Pipeline

For a Git root, candidate discovery runs `git ls-files --cached --others --exclude-standard`; otherwise it performs a deterministic filesystem walk. Both modes sort repository-relative paths, exclude generated/vendor directories including `.repo-dive/`, apply explicit include/exclude patterns, reject non-regular files and symlink traversal, and read with `O_NOFOLLOW` when the platform provides it.

The scanner records SHA-256 content hashes and classifies files as `read` or `skipped`. Stable skip reasons cover oversized, binary, invalid UTF-8, and unreadable files. The inventory fingerprint includes scan mode, ordered file metadata, hashes, statuses, and the maximum file size.

Parser selection is implemented as follows:

- Python uses the standard-library AST adapter.
- JavaScript, JSX, TypeScript, and TSX use Tree-sitter adapters.
- Unsupported languages, documentation, and syntax failures fall back to the text parser with diagnostics.
- The normalization pipeline splits every Chunk to at most `max_chunk_lines` (default `200`), removes duplicate identities, and sorts Chunks, Symbols, Relationships, and diagnostics deterministically.

## Local RAG Data Flow

<!-- contract-section:rag-boundary -->

```text
repository bytes
  -> candidate inventory + repository_fingerprint
  -> language parser -> Chunks + Symbols + Relationships
  -> SQLite BM25 + graph + optional Vector rows
  -> lexical + structural + optional vector candidates
  -> weighted_rrf + overlap deduplication
  -> complete Evidence items under token_budget
  -> calling model generates prose
  -> CLI validates Evidence IDs and persists Wiki page state
```

This split is still RAG: retrieval augments the calling model's generation, but the deterministic retrieval process and probabilistic generation process are intentionally separate.

### BM25 channel

The lexical corpus is rebuilt for every new index generation from current Chunks. The code-aware tokenizer is `code-v1`; it preserves whole code tokens and also emits case-folded, separator-split, and camel-case variants. Defaults are `k1 = 1.2` and `b = 0.75`. SQLite stores terms, document frequencies, postings, document lengths, and aggregate statistics.

### Structural channel

SQLite stores Symbols and `calls`, `contains`, `imports`, and `inherits` Relationships. Structural retrieval first performs normalized exact/prefix/substring Symbol matching, then expands a bounded, bidirectional graph traversal of depth `1` with a default minimum confidence of `0.75`. It returns definition Chunks when available and preserves relationship-path reasons.

### Vector channel

Vector retrieval is optional. `--embedding-model` selects the implemented Sentence Transformers adapter, which is lazy-loaded from the `vector` extra with `local_files_only=True` and `trust_remote_code=False`. Provider name, an opaque `local:<sha256>` model identity, and dimensions define the vector space without persisting the private absolute model path.

Index Schema 4 stores one fixed-length little-endian float32 BLOB per Chunk. The row also binds `chunk_id`, `chunk_hash`, provider, model, and dimensions. Non-finite values, dimension mismatches, mixed identities, and stale Chunk hashes are rejected. Exact brute-force cosine search at persisted float32 precision is the deterministic reference, with ties ordered by Chunk ID.

Unchanged vectors are reused only when both provider identity and Chunk content hash match. `strict` vector failure aborts publication or search; `degraded` omits the vector identity/channel and continues with lexical plus structural evidence while returning a safe warning/error code.

The `search` and `context` commands can select this provider. The current `wiki evidence` application service does not inject an Embedding Provider, so its implemented retrieval path is BM25 plus structural search even when the published index contains vectors.

### Fusion and context

Lexical and structural ranks always participate with weight `1.0`; a ready vector channel adds weight `1.0`. The strategy name is `weighted_rrf`, with `rrf_k = 60` and overlap threshold `0.8`. Results retain raw channel scores plus rank, weight, contribution, symbol-match, and relationship-path reasons. Overlapping Chunks are deduplicated after fusion.

`EvidencePacker` reserves tokens for the envelope and item metadata, ranks implementation Chunks before file-level fallback Chunks, limits each file to two selected items by default, and never slices a Chunk. It reports `estimated_tokens`, `reserved_tokens`, `truncated`, and excluded candidates with `duplicate`, `budget`, or `low_score` reasons.

<!-- contract-section:index-storage -->
## SQLite and Index Publication

The active index is a symlink to an immutable generation:

```text
<repository>/.repo-dive/
├── index -> index-generations/<build-id>
└── index-generations/
    └── <build-id>/
        ├── index.sqlite3
        ├── manifest.json
        └── metadata.json
```

The physical database path is `.repo-dive/index-generations/<build-id>/index.sqlite3`; consumers use the stable pointer path `.repo-dive/index/index.sqlite3`. `manifest.json` records Schema `1.0`, build ID, repository fingerprint, scan mode, build parameters, file-to-Chunk membership, counts, and optional embedding identity. The generation-local `metadata.json` is the public pointer summary for that index generation and is distinct from the Wiki metadata file at `.repo-dive/metadata.json`.

SQLite Schema 5 is declared by `PRAGMA user_version = 5` and contains `files`, `symbols`, `chunks`, `relationships`, `terms`, `postings`, `stats`, and `vectors`. Relationship rows preserve exact syntax-occurrence provenance while graph traversal groups them into unique endpoint-and-kind adjacencies. Foreign keys and integrity checks must pass before publication.

An index build creates a staging directory, reuses unchanged parse results from a compatible previous generation, writes and validates the complete new database and metadata, moves staging to `index-generations/<build-id>`, then atomically replaces the `.repo-dive/index -> index-generations/<build-id>` symlink. A failed build or pointer replacement preserves the previous generation and removes temporary data. Read-only commands rescan with the persisted build parameters and return `index_stale` when the repository fingerprint differs.

## Wiki Persistence and Recovery Boundary

Wiki state uses strict Schema `2.0` JSON in `.repo-dive/wiki.json` and `.repo-dive/metadata.json`. Complete files are serialized and atomically replaced; malformed, unsupported, or incomplete state is rejected without repair. `.repo-dive/wiki.md` is replaced only after all pages and Evidence are validated, and identical bytes produce `changed: false`.

Evidence freshness is page-local: the index Schema must still be `4`, and every persisted reference must match its current Chunk ID, content hash, path, and inclusive line range. The index build ID is audit provenance, not by itself a global invalidation signal.

## Knowledge Map Boundary

The optional Knowledge Map is a strict Schema `1.0` document at `.repo-dive/knowledge-map.json`. It derives repository, module, file, and symbol facts plus architecture, static-flow, and reading-tour projections from one current published index. Source Chunks remain Evidence references rather than fact nodes. A deterministic build is useful with empty semantic sections and never calls a model.

All writers use `.repo-dive/knowledge-map.lock`, a bounded OS advisory lock, followed by under-lock index revalidation, exact-intent equivalence, revision/hash compare-and-swap, complete candidate validation, byte-capacity enforcement, and atomic replacement. `artifact_revision` advances only on byte-changing writes. Deterministic changes clear semantic state; compliant capacity-only changes preserve it. `map show` and `map validate` are read-only.

Optional scope Evidence and claim enrichment use the same writer. Every claim owns fact-node and Evidence references. Validation checks schema, ownership, referential integrity, and Evidence freshness; `semantic_entailment_checked` is always `false`, so citation presence is not a truth or entailment score. Knowledge Map does not alter or feed Wiki Schema `2.0`, templates, commands, or artifacts.

## Error and Security Boundaries

- Exit code `2` represents invalid invocation or input, `3` a repository/state condition, and `4` a safe internal failure.
- stdout remains one machine-readable document; stderr contains only a concise safe diagnostic and never source Evidence.
- Repository-relative inputs reject absolute paths, Windows drives, `..`, and symlink escapes.
- Corrupt SQLite/JSON is never silently rewritten. Index and Wiki publication preserve the last valid artifact on failure.
- Network access is not part of the implemented default or Vector path; the current embedding provider accepts local model files only.
