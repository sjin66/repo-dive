# Knowledge Map Final Integration Corrections Design

## Boundary

This is primarily a release-evidence correction. Expected product files are limited to
existing tests, matched architecture documentation, and one Map-root sanitization line
in `src/repo_dive/cli.py`. Any other runtime behavior inconsistent with the frozen
parent matrix is a product-contract finding and returns the task to planning.

## Map Index-Path Sanitization

`load_published_index` emits `index_not_found` with an absolute internal index path.
That detail remains useful to existing non-Map consumers, so changing the indexing
domain error would widen compatibility impact. The root `_map_error_details` adapter is
already the boundary that adds Map recovery fields and removes absolute `path` details
for repository-selector errors.

Add `index_not_found` to that existing Map-only path-removal set. This keeps the stable
code, message, exit, retry mode, and recovery action; removes only the unsafe path from
Map output; and leaves search/context/Wiki and direct domain callers unchanged. Unit
coverage pins both sides of this boundary, while the six real process fixtures prove
the public result.

## Real-Path Error Matrix

### Resolved Contract Decision

The frozen parent matrix assigns `knowledge_map_validation_failed` to `map validate`
for reference/order/revision/Evidence invariant failures. The implemented ownership
boundaries instead classify malformed or invariant-invalid persisted bytes as
`knowledge_map_invalid`; source and Evidence freshness failures have their own stable
codes. The only owning producer of `knowledge_map_validation_failed` is writer candidate
revision validation in `MapWriteTransaction.commit()`, which `map validate` never calls.

The approved correction removes the unreachable applicability assignment rather than
adding a second read-time classification. `map validate` retains reachable not-found,
stale, invalid, and Evidence-stale outcomes. `knowledge_map_validation_failed` remains
a writer-only candidate-revision contract and remains documented as a stable public
error. This agrees with the backend executable contract and requires no additional
runtime change.

Retain one canonical expected-cell set derived from the parent applicability matrix.
Each process case invokes `repo_dive.cli.main` with a complete public command and uses a
condition-specific fixture or narrow fault seam:

| Error family | Required trigger boundary |
|---|---|
| invocation | Real argparse and strict budget/submission decoders |
| repository/input path | Real missing, non-directory, confined, unavailable path fixtures or the lowest filesystem read seam |
| index state | Real absent index, source mutation for stale state, or validated published-index seam for replacement races |
| map state | Real absent, malformed/rehash-invalid, or index-mismatched artifact bytes |
| scope/Evidence/reference/capacity | Valid built map plus deliberately constructed current snapshots, submissions, capacities, and source/index changes |
| lock/CAS/index race/write | `MapStore` transaction, lock adapter, under-lock revalidation, or atomic replacement seam after the public service has executed |
| internal operation | The narrow derivation/read/projection operation that unexpectedly fails, not the public command handler or service entry method |

Parameterization may share setup code, but every expected command/error pair remains a
separate pytest case and asserts its exact process contract. A coverage assertion
compares the executed case keys with the normative expected set. A source-level guard
or direct review assertion rejects patches of `MAP_COMMAND.handler` and public
`KnowledgeMapBuildService.build`, `KnowledgeMapEvidenceService.collect`, or
`KnowledgeMapEnrichmentService` entry methods that only raise target errors.

No-write checks hash or retain exact artifact bytes before invocation. Read-only cases
assert no artifact creation where appropriate. Precedence fixtures combine at least the
documented parser/path/index/map and under-lock-index/CAS conflicts and assert the first
normative error.

## Coordinated Enrichment Writer

Build a valid map, collect current Evidence, and prepare a valid enrichment payload.
Coordinate entry into the existing `MapStore.write_transaction` from enrichment and a
different writer with a `Barrier`; do not sleep. Both operations begin from the same
baseline but submit non-equivalent intents.

The assertion is outcome-independent:

- exactly one operation succeeds and exactly one returns
  `knowledge_map_revision_conflict`;
- the artifact revision advances exactly once;
- strict artifact decoding succeeds;
- persisted deterministic and semantic sections equal one complete expected winner
  state rather than a merge or partial write;
- pre-existing semantics are preserved or replaced exactly according to the winning
  public operation.

This augments, rather than replaces, build/reset, build/Evidence, POSIX contention,
equivalence-before-CAS, atomic preservation, and Windows adapter tests.

## Semantic Growth And Capacity

Use real scope contracts and Evidence. Grow accepted semantic state across scopes or
within a complete scope replacement until the selected persisted capacity is exactly
used. At each step assert artifact bytes remain within `artifact_byte_budget` and all
count/reference/input usage is at or below its named limit.

Replay the final accepted enrichment with a stale expected revision and identical
canonical content; equivalence must win before CAS, return unchanged, and preserve
bytes. Then exceed one named semantic capacity by the smallest observable unit. The
operation must return its stable capacity error and preserve the last accepted bytes.
No test asserts elapsed time.

## Documentation Contract

Change only the Index Manifest constant at the matched architecture lines from `1.0`
to `2.0`. Extend the existing documentation/repository contract test to compare both
language files against executable constants for:

- Index Manifest Schema `2.0`;
- SQLite Schema `5`;
- Wiki Schema `2.0`;
- Knowledge Map Schema `1.0`.

## Verification And Isolation

Working-tree checks may encounter ignored Host payloads. Release evidence is produced
from an explicit allowlist in a temporary clean worktree containing `HEAD` plus only
this child. Run both `--no-respect-gitignore` Ruff commands there, where local Host
payloads and `.codegraph/` do not exist. The current worktree is checked before and
after to prove those paths remain untouched.

## Rollback

- Error tests can be reverted independently because they do not change runtime code.
- Concurrency/performance tests can be reverted without changing persisted artifacts.
- Documentation and its parity assertion revert as one pair.
- A failed clean-snapshot gate blocks archival; it never justifies modifying ignored
  Host files or weakening Ruff coverage.
