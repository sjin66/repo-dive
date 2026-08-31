# Map CLI, Documentation, And Evaluation Design

## Command Adapter

`src/repo_dive/commands/map.py` configures and dispatches the six approved subcommands. `src/repo_dive/cli.py` only registers the `MAP_COMMAND`; existing process envelope/error translation remains authoritative.

Command table:

| Command | Domain service | Required input |
|---|---|---|
| `map build` | deterministic build | repository, source fact budget, artifact byte budget, strict budget file |
| `map show` | pure view | repository, view enum, max results |
| `map evidence` | Evidence service | repository, scope ID, token budget |
| `map enrich` | enrichment service | repository, bounded JSON file/stdin |
| `map reset` | enrichment reset | repository, scope ID |
| `map validate` | strict artifact/freshness validation | repository |

No `map status` is added. Show responses contain bounded identity, coverage, truncation, artifact/semantic counts, and revision; validate owns health.

## Input Boundaries

- Budget and enrichment files use exact bounded UTF-8 JSON parsing, one complete document, strict duplicate/unknown-field rejection, and repository-confined file paths; stdin is accepted only where specified.
- CLI positive integers use shared validators and supported upper bounds.
- Input limits are checked before expensive decoding.
- Domain modules receive typed values and never inspect argparse/environment/terminal state.

## Output Contract

JSON uses the existing result/error envelope. The command field is `map build`, `map show`, etc., consistent with existing command naming. Results expose revisions, hashes, changed/unchanged, included/omitted counts, semantic availability, and recovery-relevant IDs without source-text diagnostics.

Markdown may remain a presentation option only if existing command conventions require it and the child implements a bounded deterministic summary. It is never the artifact or required Version 1 publication format. JSON support is mandatory.

## Error Integration

The parent design matrix is normative. CLI parsing/schema errors map to exit `2`; current repository/index/map/Evidence/reference/budget state errors map to exit `3`; unexpected operation/serialization/write errors map to exit `4`.

Every checked cell in the parent command/error applicability matrix is an independent parameterized test case. Every error test captures:

- command and stable code;
- exit code;
- stdout JSON and stderr safety;
- artifact bytes before/after;
- closed `retry_mode` value;
- recovery action string/fields.

Tests assert the closed `retry_mode`/`recovery_action` enums in existing `error.details`, not message prose. Multi-failure fixtures pin each parent precedence boundary, including CLI/build invocation errors, repository/input paths, enrichment payload validation, index/map state, domain/capacity before lock, post-lock index replacement before exact equivalence/CAS, and candidate/write failures last. They explicitly prove malformed enrichment never emits generic `invalid_invocation`.

Commands do not automatically retry a revision conflict because repeating without reloading intent could overwrite a correction.

## Evaluation Design

Evaluation cases distinguish mechanical validation from semantic quality:

| Metric | Automated meaning |
|---|---|
| Citation validity | Every claim has known scope-owned Evidence IDs |
| Referential integrity | Every deterministic/semantic reference resolves to allowed current IDs |
| Evidence freshness | Snapshot chunk/index/deterministic identities match current state |
| Deterministic reproducibility | Canonical deterministic bytes/hashes/order repeat exactly |
| Semantic usefulness | Explicit expected/manual fixture judgment; not inferred from citations |

Coverage/truncation is reported separately. No metric named “100% grounding precision” is used to imply truth or entailment.

Fixture matrix includes repeated occurrences, linear flow, cycles, no roots, sparse mixed-language facts, too-small token/snapshot/reference/claim/artifact budgets, deterministic no-op/capacity/rebuild transitions, capacity-reduction conflict, current/stale semantic claims, lock contention/revision conflict, and write failure.

## Security And Recovery

Process tests cover repository path validation, symlink escape, absolute/path traversal input, oversized documents, malformed encoding/JSON, duplicate keys, private source diagnostics, contention, interrupted writes, and stale index/map/Evidence. Existing map bytes are hashed before/after every expected failure.

Show/validate are proven read-only. Build/evidence/enrich/reset are proven to use the same lock/revision behavior through externally observable conflicts.

## Documentation

Implementation-time matched pairs:

- `docs/en/architecture.md` / `docs/zh-CN/architecture.md`;
- `docs/en/cli-contract.md` / `docs/zh-CN/cli-contract.md`;
- `docs/en/knowledge-map-workflow.md` / `docs/zh-CN/knowledge-map-workflow.md`.

Headings, commands, enums, versions, paths, budgets, error codes/exits/recovery, lock/revision behavior, Evidence claim limits, validation limits, and no-Wiki statements remain equivalent. Existing Wiki instructions remain unchanged except an optional independent Knowledge Map note if necessary.

## Tooling And Release Boundary

No Agent plugin/skill is introduced. The active tooling-integration spec requires repository-owned referenced paths to exist in the same staged snapshot, `.trellis` exclusion to remain exact, staging to use an allowlist, and clean temporary-worktree Make checks. Independent `docs/superpowers` comparison files are not edited or staged by this task.

## Rollback

Remove command registration first; internal domain code/artifacts remain diagnosable and are never deleted automatically. Documentation must not remain claiming commands exist after rollback. Existing commands and Wiki behavior remain unaffected.
