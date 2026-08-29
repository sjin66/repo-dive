# Agent Plugin Installation

The `repo-dive` Agent plugin supplies one portable Agent Skill named `wiki`.
It orchestrates the separately installed `repo-dive` Python CLI; installing the
plugin does **not** install the executable or a model provider.

## Prerequisites

- A local Git repository to document. The skill never clones a URL without
  separate user authorization.
- A working `repo-dive` executable on `PATH`. Verify it with
  `repo-dive --version` and `repo-dive wiki --help`. For a source checkout,
  `make setup` creates `.venv/bin/repo-dive`; add that environment to `PATH`.
- Node.js and npm only when using the alternative third-party `skills` installer.
- A supported host version that implements Agent Skills. Packaging conventions
  change quickly, so pin the plugin source to a release tag or commit in
  reproducible environments.

## Install in a project

From the target project's root, use the separately installed Python CLI. This
project-scoped route is offline and requires neither Node.js nor a source
checkout:

```bash
repo-dive init . --agent claude-code --agent codex --agent opencode \
  --agent gemini-cli --agent github-copilot
```

Bare `repo-dive init` presents a multi-select prompt in a terminal and asks for
confirmation before writing. Automation must repeat `--agent`; JSON and
non-TTY use without an Agent fail rather than waiting for input:

```bash
repo-dive init /path/to/project --agent codex --agent opencode --format json
```

An identical rerun reports `reused`. Different existing content is preserved
and reported as a conflict; use `--force` only after reviewing it. The command
deduplicates the shared `.agents/skills/wiki` destination.

As an alternative, the third-party `skills` CLI installs the same authoritative
`skills/wiki` directory for all five supported hosts:

```bash
npx skills add OWNER/repo-dive --skill wiki \
  -a claude-code -a codex -a opencode -a gemini-cli \
  -a github-copilot -y
```

Replace `OWNER/repo-dive` with the Git repository or a local checkout path. The
project mappings are:

| Host | Installed discovery path | Invocation/discovery |
| --- | --- | --- |
| Claude Code | `.claude/skills/wiki` | `/wiki` |
| OpenAI Codex CLI | `.agents/skills/wiki` | `$wiki` or `/skills` |
| OpenCode | `.agents/skills/wiki` | Model-visible `skill` tool |
| Gemini CLI | `.agents/skills/wiki` | Skill activation with consent |
| GitHub Copilot | `.agents/skills/wiki` | `/wiki` or `/skills info wiki` |

The third-party installer normally keeps one canonical project copy and creates host
symlinks. Use `--copy` only where symlinks are unsuitable. Do not edit installed
copies independently; update from the package source instead.

Inspect before installing with `npx skills add OWNER/repo-dive --list`. Update
tracked installs with `npx skills update`. The third-party installer collects
telemetry unless `DISABLE_TELEMETRY=1` or `DO_NOT_TRACK=1` is set.

## Native and host-specific routes

The common project install above is the supported route for OpenCode. Its
JavaScript/TypeScript plugin API is a different capability and is intentionally
not used.

- **Claude Code:** validate or develop this checkout with
  `claude plugin validate .` and `claude --plugin-dir .`. A native plugin
  exposes `/repo-dive:wiki`. Marketplace publication is not part of this
  release.
- **Codex:** the built-in `$skill-installer` can install `skills/wiki` from a
  Git repository. Codex also recognizes this package's
  `.codex-plugin/plugin.json`; native marketplace installation remains
  version-sensitive and should be smoke-tested with the selected Codex build.
- **Gemini CLI:** install the standalone skill with
  `gemini skills install https://github.com/OWNER/repo-dive.git --path skills/wiki --scope workspace`
  or install the extension with
  `gemini extensions install https://github.com/OWNER/repo-dive --ref TAG`.
- **GitHub Copilot:** use
  `gh skill install OWNER/repo-dive wiki --agent github-copilot --scope project`
  with GitHub CLI 2.90.0 or newer, or
  `copilot plugin install OWNER/repo-dive` for the root Agent Plugins manifest.

## Use and output

Ask the host to generate or refresh a repository Wiki, or invoke `wiki` using
the host syntax above. The skill checks the executable first, uses JSON CLI
mode, preserves the existing working tree, and delegates prose generation to
the current Agent model. After a successful build, consume:

```text
<repository>/.repo-dive/wiki.md
```

## Uninstall and rollback

For `repo-dive init`, rollback removes only the installed project directories
after checking they contain the expected skill:

```bash
rm -rf .claude/skills/wiki .agents/skills/wiki
```

For the third-party installer, remove the project skill from all selected hosts:

```bash
npx skills remove wiki \
  -a claude-code -a codex -a opencode -a gemini-cli \
  -a github-copilot -y
```

Native routes use their host commands:

```bash
gemini skills uninstall wiki --scope workspace
gemini extensions uninstall repo-dive
copilot plugin uninstall repo-dive
```

The preview `gh skill` command currently has no uninstall subcommand. For that
route, run `gh skill list`, verify the installed skill's source, and remove only
its project directory at `.agents/skills/wiki`. Removing the Agent skill does
not uninstall the Python CLI and does not delete an existing `.repo-dive/`
directory. Review `git status --short` after rollback and preserve unrelated
changes.

## Compatibility limitations

- Project-scoped installation is supported across all five hosts. A global
  Codex install through the third-party `skills` CLI is not claimed because its
  documented destination differs from Codex's current official user path.
- Invocation and name-collision precedence differ by host. Claude native
  plugins namespace the skill as `/repo-dive:wiki`; other hosts may prefer an
  existing project or personal `wiki` skill.
- Native plugin caches may copy packages, so all resources intentionally remain
  under `skills/wiki/`.
- Claude strict validation treats this combined CLI/plugin repository's root
  `CLAUDE.md` as an unloaded compatibility file. Normal plugin validation
  succeeds; validate a staged plugin-only archive when strict validation is a
  release requirement.
- Vendor CLI smoke tests require installed, pinned clients and are not part of
  the default offline Python test suite.
