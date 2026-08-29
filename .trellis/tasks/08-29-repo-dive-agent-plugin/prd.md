# Repo Dive agent plugin

## Goal

Provide an installable Agent plugin package named `repo-dive` so users can give
supported coding agents a consistent, evidence-grounded Wiki generation
workflow backed by the existing `repo-dive` CLI.

## Background

- `repo-dive` is a deterministic local RAG CLI; the calling Agent, not the CLI,
  plans the Wiki structure and generates page prose.
- The repository already contains a reusable Agent Skill at
  `.agents/skills/repo-dive/SKILL.md` and its detailed workflow reference at
  `.agents/skills/repo-dive/references/workflow-contract.md`.
- The existing skill implements the intended Wiki orchestration but is a
  repository-local skill named `repo-dive`, not a separately installable plugin
  containing a `wiki` skill.
- The CLI package is already named `repo-dive` and exposes the `repo-dive`
  executable. The plugin must use the same package name without implying that
  installing the Agent plugin also installs the Python CLI unless that behavior
  is explicitly designed.

## Requirements

- The Agent plugin package name must be `repo-dive`.
- The package must support installation by multiple Agent platforms through a
  documented, reproducible mechanism.
- The initial first-class platform set is Claude Code, OpenAI Codex CLI,
  OpenCode, Gemini CLI, and GitHub Copilot CLI/coding agent.
- The package must initially expose one skill named `wiki`.
- The `wiki` skill must guide the calling Agent through the implemented,
  resumable CLI workflow: preflight, index, structure, per-page evidence and
  generation, page submission, status, and build.
- The skill must preserve the product boundary: it may invoke the local CLI and
  use the current Agent model, but must not claim that the CLI invokes a model.
- The skill must use JSON CLI mode for automation, respect exit codes, preserve
  existing repository changes, and avoid silently installing software or
  cloning remote repositories.
- Shared skill content should have one authoritative source to prevent behavior
  drift across supported Agent platforms.
- Installation and usage documentation must state the supported platforms,
  prerequisites, install commands, skill invocation, output location, and
  uninstall or rollback procedure.
- The Python CLI must expose a non-interactive `repo-dive init` command that can
  install its bundled `wiki` skill directly, without requiring Node.js, `npx`,
  network access, or a source checkout.
- Bare `repo-dive init` in a TTY must present a multi-select prompt for the five
  supported Agents and install for every selected Agent in one operation.
- Agent and CI callers must be able to bypass prompting with repeatable
  `--agent` options. JSON mode or non-TTY execution without `--agent` must fail
  validation instead of waiting for input.
- `init` must install only at project scope. User-global installation remains a
  host-specific documented route in the initial release.
- `init` must support `--format json`, use the existing process exit-code and
  stdout/stderr contracts, and report every destination as installed, reused,
  or conflicting.
- The bundled skill must be included in wheel and sdist builds and remain
  byte-equivalent to the authoritative distributable `skills/wiki` source.
- Repeated initialization must be idempotent. Existing different skill content
  must not be overwritten unless the caller explicitly passes `--force`.
- Developer-facing and user-facing documentation changes must be maintained in
  equivalent English and Simplified Chinese pairs where repository policy
  requires paired documentation.

## Acceptance Criteria

- [x] A distributable package named `repo-dive` exists with a valid `wiki`
  skill and all referenced files included.
- [x] Each declared Agent platform can install or discover the package using
  the documented command or file layout in a clean temporary workspace.
- [x] After installation, each declared platform exposes the `wiki` capability
  without requiring users to manually duplicate skill files.
- [x] The installed `wiki` skill checks for the `repo-dive` executable and
  reports a clear prerequisite failure rather than silently installing it.
- [x] The skill describes and follows the actual CLI Wiki state machine and
  generates the stable `<repository>/.repo-dive/wiki.md` artifact.
- [x] Automated checks validate package metadata/layout, required skill files,
  internal references, and platform installation mappings.
- [x] `repo-dive init --format json` installs the bundled `wiki` skill into the
  selected project Agent discovery paths without network access.
- [x] A wheel-installed CLI can run `init`; an identical rerun reports reuse,
  while conflicting content is preserved unless `--force` is supplied.
- [ ] Existing repository tests plus `make check` and `make test-all` pass.

`make test-all` passes with 416 tests. A built wheel and sdist pass the package
smoke harness, including wheel-installed `init`. `make check` is currently
blocked by 32 unrelated, pre-existing/untracked `.trellis` files that Ruff
would reformat; task-owned Python files pass focused Ruff and mypy checks.

## Key Product Decisions

- The portable `wiki` skill is the product capability. Platform-specific
  plugin or extension metadata is an installation adapter, not a separate
  implementation of the skill.
- The package supports project-scoped installation across all five target
  platforms. User-global installation may be documented only where the target
  platform's current official path agrees with the selected installer.
- The initial release prepares local and Git-based installation but does not
  publish to an external marketplace or registry.
- Bare `repo-dive init` uses an interactive multi-select prompt. Repeatable
  `--agent` is the stable non-interactive contract.

## Out of Scope

- Bundling or reimplementing the Python CLI inside the Agent plugin.
- Implicit model-provider calls, MCP server support, or remote repository
  cloning.
- Skills other than `wiki` in the initial release.
- User-global installation through `repo-dive init`.
- Publishing to an external registry or marketplace unless separately approved;
  this task can prepare a publishable package and local install verification.
