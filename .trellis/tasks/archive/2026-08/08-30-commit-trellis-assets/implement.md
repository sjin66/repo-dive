# Implementation Plan

1. Record the concurrent Wiki quality task's content hash and current Git/remote
   state as preservation baselines.
2. Extend `.git/info/exclude` with exact local rules for `skills-lock.json` and the
   three archived diagnostic tasks.
3. Fix formatting only within the intended Trellis core asset set.
4. Force-stage the ignored Trellis core through the exact allowlist in `design.md`.
5. Inspect the staged diff and verify no secret-like values or unrelated paths are
   present.
6. Create a detached temporary worktree, apply the cached diff, and run `make check`
   and `make test-all` against that exact snapshot.
7. Commit the core as `chore: add Trellis project workflow`.
8. Stage and inspect the three Wiki governance planning task directories, run the
   relevant repository checks, and commit them as task planning records.
9. Run the full quality review over all resulting commits and confirm the concurrent
   task hash is unchanged.
10. Add and review the backend tooling-integration code-spec required by Phase 3,
    including the optional/generated-path exemption, then validate and commit it.
11. Archive this task without auto-commit, stage only its archive relocation, inspect
    it, and create the final bookkeeping commit.
12. Confirm no staged files remain, local commits are ahead of `origin/main`, and no
    push occurred.

## Validation Commands

```bash
make check
make test-all
git diff --cached --check
git status --short
git log --oneline -10
```

## Rollback Points

- Before each commit: unstage only the exact allowlisted paths if validation fails.
- After a commit: do not amend or reset; create a focused follow-up commit if a
  task-scoped correction is required.
- Never modify or remove the concurrent Wiki quality task or local Host payloads.
