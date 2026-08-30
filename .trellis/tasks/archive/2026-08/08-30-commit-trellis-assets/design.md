# Design: Commit Trellis repository assets

## Boundary

This task converts the partially installed Trellis setup into a self-contained,
repository-owned core without adding Host-specific generated integrations. Product
source, tests, release artifacts, and the concurrent Wiki quality task are unchanged.

## Committed Asset Groups

### Trellis core

- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.gitattributes`
- `.trellis/.gitignore`
- `.trellis/.template-hashes.json`
- `.trellis/.version`
- `.trellis/agents/`
- `.trellis/config.yaml`
- `.trellis/scripts/`
- `.trellis/workflow.md`
- `.trellis/spec/guides/`
- `.trellis/workspace/index.md`
- `.trellis/tasks/00-bootstrap-guidelines/`

These paths form one integration unit: the instructions reference the workflow and
scripts, while configuration, metadata, guides, workspace conventions, and bootstrap
record define the project contract used by that runtime.

### Persisted plans

- `.trellis/tasks/08-29-governed-wiki-state/`
- `.trellis/tasks/08-29-markdown-ast-validation/`
- `.trellis/tasks/08-29-wiki-template-cli-integration/`

These are committed separately as planning records for the already tracked Wiki
governance parent task.

### Task closure

After verification and the focused commits, this task is archived and its archive is
committed as bookkeeping.

### Durable code-spec

- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/tooling-integration-contracts.md`

The Phase 3 spec update records the review finding that required repository-owned
tooling references must resolve in a fresh checkout. Optional Host payload examples,
generated paths, placeholders, and globs are explicitly outside that closure check.

## Local-Only Paths

The existing `.git/info/exclude` remains the mechanism for Host payloads. Add exact
local exclusions for `skills-lock.json` and the three archived diagnostic tasks. Do
not use broad task-directory exclusions and do not delete any files.

## Verification Strategy

The main worktree contains ignored duplicate Skill installations, so direct
`make test-all` does not represent the intended committed tree. Stage each intended
snapshot through an exact allowlist, apply the cached diff to a detached temporary
worktree based on `HEAD`, and run `make check` plus `make test-all` there. This tests
the precise commit candidate without moving or deleting unrelated local files.

Before each commit, inspect staged status, staged diff, recent log, and secret-like
content. Remove the temporary worktree after verification. No remote operation is
performed.

## Rollback

If validation fails, leave commits and remotes unchanged, unstage only the exact
task-owned paths, and fix only defects within those paths. Never reset, restore, or
delete unrelated worktree content.
