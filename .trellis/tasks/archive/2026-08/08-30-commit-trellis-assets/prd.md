# Commit Trellis repository assets

## Goal

Classify, validate, and commit repository-owned Trellis configuration, specifications, and task records while excluding local-only agent payloads.

## Background

- `AGENTS.md` now declares Trellis project management and references
  `.trellis/workflow.md`, `.trellis/scripts/`, specs, tasks, and workspace records.
- The workflow and scripts are currently hidden by local `.git/info/exclude`; committing
  the instructions without this core runtime would leave fresh clones incomplete.
- Host-specific generated payloads account for most of the original changes and are
  not required in the repository-owned core.
- A separate `08-30-enhance-wiki-structure-quality` task is active in another session
  and must remain untouched.

## Requirements

- Commit a self-contained Trellis core: the tracked instruction updates,
  `.gitattributes`, project configuration/version/template metadata, Trellis agents,
  scripts, workflow, shared guides, workspace index, and bootstrap task.
- Commit the three existing Wiki governance child-task plans so their tracked parent
  does not reference local-only planning state.
- Keep host-specific `.agents/`, `.claude/`, `.cursor/`, `.dsh/`, `.opencode/`, `.pi/`,
  and generated `.github/` Agent payloads local-only.
- Do not commit `skills-lock.json` while its corresponding Skill payloads remain
  local-only.
- Do not commit the three archived read-only diagnostic tasks; hide those exact paths
  locally rather than deleting them.
- Do not modify, stage, commit, or locally hide
  `.trellis/tasks/08-30-enhance-wiki-structure-quality/`.
- Correct only formatting defects in the intended committed files.
- Capture the repository-owned tooling closure rules learned during review in a
  backend code-spec, while explicitly exempting optional Host examples and generated
  local paths from required-path validation.
- Stage files through exact allowlists and keep unrelated workspace changes intact.
- Create focused local commits with repository-style messages; do not push.

## Acceptance Criteria

- [x] A fresh checkout at the resulting commits contains every required
      repository-owned path referenced by the committed Trellis instructions;
      identified optional/generated examples, placeholders, and globs are exempt.
- [x] Host-specific Agent payloads, `skills-lock.json`, and the three diagnostic task
      archives are absent from the commits.
- [x] The Wiki governance planning tasks and bootstrap record are persisted.
- [x] `make check` and `make test-all` pass against the exact staged snapshot from a
      clean temporary worktree.
- [x] No secrets or unrelated files are staged, and the separate Wiki quality task is
      byte-for-byte untouched.
- [x] The backend spec records the executable fresh-checkout validation contract and
      distinguishes required repository paths from optional Host examples.
- [x] The resulting commits remain local and are not pushed.

## Out of Scope

- Changing Repo Dive product behavior or tests.
- Committing every generated Host integration.
- Completing or revising the planned Wiki governance tasks.
- Cleaning or deleting local Agent installations.
- Pushing, merging, tagging, or opening a pull request.

## Notes

- The user selected local exclusions for Host payloads and approved following the
  recommendation to commit only repository-owned assets.
