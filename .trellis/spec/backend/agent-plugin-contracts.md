# Agent Plugin Contracts

## Scenario: Portable Agent Skills Package

### 1. Scope / Trigger

Use this contract when adding or changing an Agent-facing capability distributed
from the `repo-dive` repository. The package targets Claude Code, Codex CLI,
OpenCode, Gemini CLI, and GitHub Copilot while keeping the Skill separate from
either a PATH-installed CLI or an explicitly installed self-contained runtime.

### 2. Signatures

The portable skill entry point is:

```text
skills/<skill-name>/SKILL.md
```

The initial package surface is:

```text
skills/wiki/SKILL.md
plugin.json
.claude-plugin/plugin.json
.codex-plugin/plugin.json
gemini-extension.json
```

The shared project-scoped install command is:

```bash
npx skills add OWNER/repo-dive --skill wiki \
  -a claude-code -a codex -a opencode -a gemini-cli \
  -a github-copilot -y
```

The built-in project installer is:

```text
repo-dive init [repository] [--agent AGENT]... [--force]
               [--format json|markdown]
```

The self-contained runtime launchers are:

```text
skills/wiki/scripts/repo-dive [--install | <repo-dive arguments>...]
skills/wiki/scripts/repo-dive.ps1 [--install | <repo-dive arguments>...]
```

Both consume `skills/wiki/references/release.json`, whose required fields are
`schema_version`, `version`, `repository`, `tag`, and a `targets` entry with
`archive`, `archive_type`, `top_level`, and `executable`.

### 3. Contracts

- `skills/wiki/SKILL.md` is the only committed operational source for `wiki`.
- Skill frontmatter contains portable Agent Skills fields. `name` must equal the
  parent directory name.
- Every relative resource reference resolves inside `skills/wiki/`.
- Every plugin manifest uses package name `repo-dive` and the Python package
  release version.
- `plugin.json` uses Agent Plugins v1; Claude, Codex, and Gemini keep only thin
  host metadata in their native manifests.
- OpenCode uses Agent Skills discovery. Do not create a JavaScript runtime
  plugin solely to distribute a skill.
- Installing the Agent package never downloads the CLI, clones a source
  repository, or invokes a model provider implicitly. If no compatible CLI is
  on `PATH`, first use must obtain explicit consent before the Skill runs its
  version-pinned bootstrap installer.
- Release metadata supports only `darwin-arm64`, `darwin-x64`, and
  `windows-x64`. The launcher rejects every other target before network access.
- Release version checks compare `GITHUB_REF_NAME` only when
  `GITHUB_REF_TYPE=tag`; branch CI must run the same repository checks without
  treating the branch name as a release version.
- Bootstrap archives are PyInstaller `onedir` directories. Launchers verify the
  exact SHA-256 manifest entry, reject unsafe paths and links, smoke the CLI,
  and atomically publish a completed directory to a versioned user cache.
- Published archives contain only regular files. The archive builder rejects
  source links that resolve outside the bundle, flattens bundle-local file
  aliases, and omits bundle-local directory aliases whose canonical contents
  are already archived. This is required for PyInstaller's macOS
  `Python.framework` layout to satisfy the link-free bootstrap contract.
- Normal launcher execution never downloads and forwards arguments, standard
  streams, and process status unchanged. The Skill installation directory may
  be read-only.
- Bare `init` may prompt only when stdin is a TTY and output is Markdown.
  JSON/non-TTY callers must provide repeatable `--agent` arguments.
- Claude installs to `.claude/skills/wiki`; Codex, OpenCode, Gemini, and Copilot
  share `.agents/skills/wiki`. Deduplicate destinations before writing.
- All destinations must pass conflict and symlink checks before any write.
  Changed destinations are staged and published atomically; a later failure
  restores every earlier destination or preserves recovery backups.
- Hatch force-includes root `skills/wiki` under `repo_dive/_skills/wiki` in the
  wheel. Package smoke tests require every bundled file to match source bytes.

### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| `repo-dive` is absent from `PATH` | Skill explains the pinned bootstrap and requires explicit consent. |
| Compatible CLI and cache are absent | Explain source/version/cache and ask for consent; never download implicitly. |
| Host is not a supported release target | Stop before network access with an actionable platform diagnostic. |
| Branch CI sets `GITHUB_REF_NAME` | Run release metadata checks without tag/version comparison. |
| Tag ref is missing, malformed, conflicting, or version-mismatched | Fail the release contract check before building assets. |
| Digest, archive safety, extraction, or smoke fails | Publish nothing and preserve every older cache. |
| A manifest name or version differs | Package contract test fails. |
| A relative skill link escapes `skills/wiki/` | Package contract test fails. |
| A second committed `wiki` skill appears in a host discovery root | Single-source contract test fails. |
| Functional CLI command exits non-zero | Do not advance; recover using exit code and stable JSON error code. |
| User supplies a repository URL | Do not clone without separate authorization. |
| JSON/non-TTY `init` omits `--agent` | Exit `2` with `agent_required`; never read stdin. |
| Interactive selection is empty/invalid or cancelled | Exit `2` with a stable invocation error; write nothing. |
| Destination contains a symlink | Exit `2` with `skill_conflict`; do not follow or replace it. |
| Existing skill matches bundled bytes | Return `reused`; perform no write. |
| Existing skill differs without `--force` | Exit `2` with `skill_conflict`; preserve all bytes. |
| Multi-destination publication fails | Roll back all published destinations; retain recovery backup if rollback itself fails. |

### 5. Good/Base/Bad Cases

- Good: add a reference under `skills/wiki/references/` and link it relatively
  from the authoritative skill.
- Base: add a new portable skill as `skills/<name>/SKILL.md`, then extend package
  tests and documentation without copying it into host directories.
- Bad: commit separate `.claude/skills/wiki` and `.agents/skills/wiki` bodies or
  make plugin installation run `pip install` silently.
- Good: `repo-dive init --agent claude-code --agent opencode --format json`
  installs two deduplicated destinations without prompting.
- Bad: prompt in JSON mode, replace a symlink target, or publish the Claude
  destination before checking a conflict in the shared destination.

### 6. Tests Required

`tests/unit/test_agent_plugin.py` must assert:

- portable frontmatter and exact skill identity;
- one authoritative skill per capability;
- resource closure inside the skill root;
- manifest package identity and version consistency;
- the CLI/model execution boundary and complete JSON Wiki stage sequence;
- equivalent English and Simplified Chinese installation mappings.
- TTY selection/cancellation and non-TTY/JSON no-prompt behavior;
- destination deduplication, reuse, conflict, `--force`, symlink rejection, and
  multi-destination rollback;
- wheel/sdist resource inclusion and wheel-installed `init` execution.
- release metadata/version/target consistency and unsupported-target rejection
  before network access;
- explicit launcher installation, archive traversal rejection, cache
  publication, argument forwarding, and exit-code propagation;
- native bundle archive layout and extracted JavaScript/TypeScript grammar
  smoke coverage.
- PyInstaller-style framework file/directory aliases, link-free archive
  members, and rejection of source links that escape the bundle.

Run:

```bash
python3 -m pytest tests/unit/test_agent_plugin.py -q
python3 -m pytest tests/unit/test_package_smoke.py -q
python3 scripts/check_repo_contract.py
python3 scripts/check_release_contract.py
make check
make test-all
```

Vendor CLI smoke tests are additional evidence, not default offline test-suite
dependencies. Record exact client versions when running them.

### 7. Wrong vs Correct

#### Wrong

```text
.claude/skills/wiki/SKILL.md
.agents/skills/wiki/SKILL.md
```

These copies drift and may produce different Wiki workflows by host.

#### Correct

```text
skills/wiki/SKILL.md
.claude-plugin/plugin.json
.codex-plugin/plugin.json
gemini-extension.json
```

All hosts consume one skill tree through standard installation or thin native
metadata adapters.

For direct CLI installation, validate every target and stage all skill trees
before publishing any destination. Never implement `--force` as an unchecked
recursive copy over an existing or symlinked directory.
