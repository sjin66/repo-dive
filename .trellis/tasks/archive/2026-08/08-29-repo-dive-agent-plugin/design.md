# Repo Dive Agent Plugin Design

## Architecture

The repository root is the distributable `repo-dive` Agent plugin package. It
contains one authoritative portable skill tree and thin metadata adapters for
platforms that define a native plugin or extension package:

```text
repo-dive/
├── plugin.json
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── gemini-extension.json
└── skills/
    └── wiki/
        ├── SKILL.md
        └── references/workflow-contract.md
```

`skills/wiki/SKILL.md` is the only operational instruction source. Every
adapter discovers or points to that same directory; platform-specific copies of
the skill are not committed.

## Package Contracts

### Portable Skill

- `skills/wiki/SKILL.md` follows the Agent Skills specification.
- Frontmatter uses portable fields only, with `name: wiki` matching the parent
  directory.
- All relative references remain inside `skills/wiki/` so copied plugin caches
  are self-contained.
- The workflow checks for the separately installed `repo-dive` executable and
  never installs software or clones a repository implicitly.

### Platform Adapters

- Root `plugin.json` follows Agent Plugins v1 and enables GitHub Copilot direct
  plugin installation.
- `.claude-plugin/plugin.json` enables Claude Code native plugin validation and
  local installation.
- `.codex-plugin/plugin.json` exposes `./skills/` to the OpenAI plugin system.
- `gemini-extension.json` enables Gemini CLI extension installation and
  convention-based skill discovery.
- OpenCode receives no JavaScript plugin: its runtime plugin API is unrelated to
  skills. It installs `wiki` through the standard skill installer into a
  documented discovery path.

All manifests use package identity `repo-dive` and the same release version.

## Installation Model

The common documented route is a project-scoped install from the Git repository
or local checkout with the `skills` CLI, selecting Claude Code, Codex, OpenCode,
Gemini CLI, and GitHub Copilot. Native routes are also documented where the
platform has an official plugin, extension, or skill installer.

The package does not install the Python distribution. Documentation treats a
working `repo-dive` executable as a prerequisite and explains the distinction
between the Agent plugin package and CLI package.

### Direct CLI Initialization

The Python distribution additionally exposes:

```text
repo-dive init [repository] [--agent AGENT]... [--force]
               [--format json|markdown]
```

- `repository` defaults to the current directory and resolves through the
  existing repository-path boundary.
- In a TTY, no `--agent` opens a multi-select prompt for Claude Code, Codex,
  OpenCode, Gemini CLI, and GitHub Copilot. The prompt accepts one or more
  selections and requires explicit confirmation before writing.
- Repeatable `--agent` makes the command non-interactive. JSON mode and non-TTY
  execution require at least one `--agent` and never read stdin.
- Claude maps to `.claude/skills/wiki`; Codex, OpenCode, Gemini, and Copilot map
  to `.agents/skills/wiki`. Shared destinations are deduplicated before writes.
- Installation is project-scoped and offline. It never shells out to `npx`, a
  vendor CLI, or a network installer.
- An identical destination is reported as reused. Different existing content
  is a validation conflict and remains byte-for-byte unchanged unless
  `--force` is supplied.
- JSON output reports selected Agents and each unique destination's path,
  mapped Agents, and `installed`, `reused`, or `replaced` status.

The root `skills/wiki` tree remains authoritative. Hatch force-includes it into
the wheel under the `repo_dive` package, and runtime code reads it with
`importlib.resources`; no second committed skill body is introduced.

## Wiki Data Flow

1. Resolve a local repository and inspect repository instructions.
2. Verify the CLI and preserve the existing working tree.
3. Run `index` in JSON mode.
4. Let the calling Agent design and submit Wiki structure.
5. For each page, collect persisted Evidence, generate grounded Markdown with
   the current Agent model, and submit exact Evidence IDs sequentially.
6. Resume from `wiki status` and recover based on stable exit/error contracts.
7. Build only after all pages are generated, then report
   `<repository>/.repo-dive/wiki.md`.

The CLI remains deterministic and never owns the generative model session.

## Compatibility

- Invocation syntax differs by host (`/repo-dive:wiki`, `$wiki`, `/wiki`, or
  model-triggered skill loading), so documentation lists platform-specific
  invocation without changing shared workflow semantics.
- Project-scoped `.agents/skills` is the safe common destination for Codex,
  OpenCode, Gemini, and Copilot. The common installer maps Claude to
  `.claude/skills`.
- Global Codex installation through the third-party `skills` CLI is not claimed
  because its documented destination differs from OpenAI's current official
  user path.
- Host versions are recorded in manual smoke evidence because these packaging
  conventions are evolving.

## Validation

Repository tests statically validate skill frontmatter, internal links,
manifest identity/version consistency, absence of duplicated skill bodies, and
documented target mappings. Optional external smoke checks validate the package
with installed platform CLIs in isolated temporary workspaces without requiring
them in the default Python test suite.

`init` tests cover TTY multi-selection, explicit non-interactive selection,
destination deduplication, idempotency, conflict preservation, forced
replacement, JSON process I/O, offline execution, and a built-wheel install.

The final required gate remains `make check` and `make test-all`.

## Rollback

The feature is additive at repository/package level. Rollback removes the four
adapter manifests, the `skills/wiki` tree, `init` command/service, package
resource mapping, related tests, and paired documentation. Existing
`.repo-dive/` artifact schemas are unchanged. Skills already installed in user
repositories remain user-owned and are not silently deleted by a code rollback.

## Trade-offs

- Thin native adapters add a few metadata files but avoid forcing every user
  through a third-party installer.
- A single skill source prevents drift but means host-only frontmatter features
  are intentionally unavailable.
- Marketplace publication is deferred; Git/local installation can be validated
  without credentials, review queues, or external release side effects.
