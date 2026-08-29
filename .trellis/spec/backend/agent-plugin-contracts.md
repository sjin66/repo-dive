# Agent Plugin Contracts

## Scenario: Portable Agent Skills Package

### 1. Scope / Trigger

Use this contract when adding or changing an Agent-facing capability distributed
from the `repo-dive` repository. The package targets Claude Code, Codex CLI,
OpenCode, Gemini CLI, and GitHub Copilot while keeping the Python CLI as a
separately installed executable.

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
- Installing the Agent package never installs the Python CLI, clones a source
  repository, or invokes a model provider implicitly.
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
| `repo-dive` is absent from `PATH` | Skill stops at preflight and reports the separate CLI prerequisite. |
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

Run:

```bash
python3 -m pytest tests/unit/test_agent_plugin.py -q
python3 scripts/check_repo_contract.py
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
