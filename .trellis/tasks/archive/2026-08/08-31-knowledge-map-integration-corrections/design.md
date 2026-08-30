# Knowledge Map Integration Corrections Design

## Boundaries

The correction touches only the boundary that owns each defect:

| Finding | Owning boundary |
|---|---|
| Map argparse failure bypasses JSON | root CLI / `commands.map` parser integration |
| Wrong-scope persisted association accepted | strict Knowledge Map artifact model validation |
| Simulated process matrix | Map integration tests with service/store seam injection |
| Incomplete writer/performance proof | existing shared store and bounded domain tests |
| Schema constants drift | matched EN/zh-CN documentation |

No deterministic derivation, semantic permission table, store protocol, or Wiki code is
redesigned.

## Invocation Error Integration

Map parser errors must be converted at the root process boundary before argparse writes
plain usage output and exits. The implementation should reuse the existing error
envelope path rather than serialize a second envelope in `commands.map`. It must retain
the nested command identity when available, sanitize diagnostics, and avoid changing
successful parsing or help output.

Tests invoke `repo_dive.cli.main` or the installed subprocess with invalid Map values.
They parse stdout as one complete JSON object and separately inspect stderr. Existing
non-Map parser tests remain the compatibility gate.

## Artifact Scope Closure

During strict artifact validation, build a scope-contract lookup and validate each
`ScopeEnrichment` against the matching contract:

- scope kind and contract hash already match;
- every claim `fact_node_id` is in `allowed_fact_node_ids`;
- every claim `related_node_id` is in `allowed_fact_node_ids`;
- every Evidence ID belongs to the scope's current snapshot.

This validation is independent of submission validation because persisted JSON is an
untrusted complete document. It must reject a rehashed malformed artifact rather than
silently remove or repair semantics.

## Process Matrix Strategy

The root parser and real `MAP_COMMAND.handler` always run. Test rows use the narrowest
realistic trigger:

- filesystem/index/map fixtures for invocation, repository, path, missing/stale/invalid
  state, scope, Evidence, capacity, and reference failures;
- monkeypatch the invoked domain service or store method, not the command handler, for
  lock, under-lock index replacement, revision, atomic write, and unexpected internal
  failures that need deterministic fault injection;
- hash artifact bytes before/after every writer failure;
- parameterize only rows with identical setup semantics while retaining one assertion
  record per checked command/cell.

This proves the public adapter and envelope without duplicating expensive domain tests.

## Concurrency And Bounded Work

Use coordinated processes/events or existing deterministic lock helpers rather than
sleeps. At least two different writer types contend for the same repository lock, and
the loser must either observe exact equivalence or a stable conflict without losing the
winner. Reuse the existing Windows lock adapter seam for branch tests.

Performance tests assert bounded counts, candidate/reference truncation, artifact-byte
failure, and stable no-growth replay. They do not assert wall-clock thresholds.

## Documentation And Historical Files

Update both language files in each affected pair. Repository contract tests should pin
Schema `5` and Wiki Schema `2.0` where stale constants were found.

`docs/superpowers` files remain byte-unchanged. Parent task notes/traceability may state
that they are historical planning comparisons superseded by the final parent contract;
no product documentation links to them as runtime authority.

## Rollback

- Invocation correction can be reverted independently while retaining all domain code.
- Scope validation rollback restores previous decode behavior but never migrates or
  rewrites artifacts.
- Tests/docs can be reverted with their owning correction; no repository-owned
  Knowledge Map artifact is deleted automatically.
