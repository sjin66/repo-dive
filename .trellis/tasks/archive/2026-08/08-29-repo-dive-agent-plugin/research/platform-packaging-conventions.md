# Research: Platform skill and plugin packaging conventions

- **Query**: Determine official/authoritative filesystem layouts, install commands, manifests, and conflicts for Claude Code, OpenAI Codex CLI, OpenCode, Gemini CLI, and GitHub Copilot coding agent/CLI.
- **Scope**: external
- **Date**: 2026-08-29

## Findings

## Claude Code

### Verified plain-skill layout

| Scope | Path |
|---|---|
| Project | `.claude/skills/wiki/SKILL.md` |
| Personal | `~/.claude/skills/wiki/SKILL.md` |
| Plugin | `<plugin-root>/skills/wiki/SKILL.md` |

Claude Code follows Agent Skills but permits additional Claude-only
frontmatter. Plain project/personal skill invocation is `/wiki`. Plugin skills
are namespaced, so plugin `repo-dive` exposes `/repo-dive:wiki` (and may expose
the unqualified name only when no conflict occupies it).

### Verified native plugin layout and manifest

```text
repo-dive/
├── .claude-plugin/
│   └── plugin.json
└── skills/
    └── wiki/
        ├── SKILL.md
        └── references/
```

If a `.claude-plugin/plugin.json` exists, only that manifest belongs inside
`.claude-plugin`; component directories remain at plugin root. `name` is the
only required manifest field. For distributable metadata, `description`,
`version`, `author`, `homepage`, `repository`, `license`, and `keywords` are
documented. `skills` is optional for the default `skills/` location.

Minimal manifest:

```json
{
  "name": "repo-dive",
  "version": "1.0.0",
  "description": "Evidence-grounded repository Wiki workflow"
}
```

Local development/validation:

```bash
claude --plugin-dir ./repo-dive
claude plugin validate ./repo-dive --strict
```

Marketplace distribution requires `.claude-plugin/marketplace.json` at the
marketplace repository root. Required catalog fields are `name`, `owner`, and
`plugins`; each plugin entry requires `name` and `source`.

```text
/plugin marketplace add OWNER/REPOSITORY
/plugin install repo-dive@MARKETPLACE-NAME
# shell equivalent, default user scope
claude plugin install repo-dive@MARKETPLACE-NAME
```

The plugin is copied into a versioned cache. Relative links escaping the plugin
directory do not work after copying. Version updates are driven by manifest or
catalog version changes, so a declared version must be bumped for releases.

Sources:

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Create Claude Code plugins](https://code.claude.com/docs/en/plugins)
- [Claude plugin reference](https://code.claude.com/docs/en/plugins-reference)
- [Claude plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Install Claude plugins](https://code.claude.com/docs/en/discover-plugins)

## OpenAI Codex CLI / ChatGPT Codex

### Verified plain-skill layout

Codex scans `.agents/skills` from current working directory upward to repository
root. It also loads user `$HOME/.agents/skills`, admin `/etc/codex/skills`, and
built-ins. Symlinked skill directories are supported.

```text
<repo>/.agents/skills/wiki/SKILL.md
~/.agents/skills/wiki/SKILL.md
```

Explicit use is `$wiki` or through `/skills`; matching descriptions can trigger
implicit activation. An optional `agents/openai.yaml` under a skill controls UI
metadata, implicit-invocation policy, and tool dependencies, but is not part of
the Agent Skills standard.

The built-in `$skill-installer` installs curated or repository skills. OpenAI
states that reusable distribution should prefer plugins.

### Verified OpenAI plugin layout and manifest

```text
repo-dive/
├── .codex-plugin/
│   └── plugin.json
└── skills/
    └── wiki/
        └── SKILL.md
```

Every OpenAI plugin has `.codex-plugin/plugin.json`. A minimal skills-only
manifest is:

```json
{
  "name": "repo-dive",
  "version": "1.0.0",
  "description": "Evidence-grounded repository Wiki workflow",
  "skills": "./skills/"
}
```

OpenAI's local marketplace locations are
`$REPO_ROOT/.agents/plugins/marketplace.json` and
`~/.agents/plugins/marketplace.json`; a legacy Claude marketplace at
`$REPO_ROOT/.claude-plugin/marketplace.json` is also read by the ChatGPT desktop
app. Marketplace management commands include:

```bash
codex plugin marketplace add OWNER/REPO
codex plugin marketplace add ./local-marketplace-root
codex plugin marketplace list
codex plugin marketplace upgrade [MARKETPLACE]
codex plugin marketplace remove MARKETPLACE
```

The official documentation says local marketplace plugins are installed and
tested through the ChatGPT desktop app; the CLI commands above manage catalogs.
Public plugins go through OpenAI review into a universal directory shared by
ChatGPT and Codex. OpenAI also accepts a skills-only Claude plugin archive with
`.claude-plugin/plugin.json` and converts it to `.codex-plugin/plugin.json`, but
Claude marketplace approval does not transfer.

Sources:

- [OpenAI: Build skills](https://developers.openai.com/codex/build-skills.md)
- [OpenAI: Build plugins](https://developers.openai.com/codex/build-plugins.md)
- [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins.md)
- [OpenAI: Submit a Claude Code plugin](https://developers.openai.com/plugins/guides/submit-claude-plugin.md)

## OpenCode

### Verified skill layout

OpenCode searches all of these locations:

```text
.opencode/skills/wiki/SKILL.md
~/.config/opencode/skills/wiki/SKILL.md
.claude/skills/wiki/SKILL.md
~/.claude/skills/wiki/SKILL.md
.agents/skills/wiki/SKILL.md
~/.agents/skills/wiki/SKILL.md
```

For project locations it walks upward from CWD to the Git worktree. It requires
`name` and `description`, recognizes `license`, `compatibility`, and string-map
`metadata`, and ignores unknown frontmatter fields. It loads a skill through
the model-visible `skill` tool rather than promising a slash-command name.

### Verified native plugin convention (different concept)

OpenCode's documented plugins are JavaScript/TypeScript modules that register
hooks/tools. They are not filesystem skill bundles and do not use a skill
package manifest.

```text
.opencode/plugins/my-plugin.ts
~/.config/opencode/plugins/my-plugin.ts
```

Published runtime plugins are npm packages listed in `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["@owner/repo-dive-opencode-plugin"]
}
```

OpenCode installs npm runtime plugins automatically with Bun and caches them
under `~/.cache/opencode/node_modules/`. There is no documented way for such an
npm plugin merely containing `skills/wiki/SKILL.md` to register that skill.
Therefore the authoritative skills-only distribution route is installation to
a discovery path, not the JS plugin mechanism.

Sources:

- [OpenCode Agent Skills](https://opencode.ai/docs/skills/)
- [OpenCode plugins](https://opencode.ai/docs/plugins/)

## Gemini CLI

### Verified standalone skill layout and installation

Gemini's precedence, low to high, is built-in, extension, user, workspace.
Locations are:

```text
~/.gemini/skills/wiki/SKILL.md
~/.agents/skills/wiki/SKILL.md
.gemini/skills/wiki/SKILL.md
.agents/skills/wiki/SKILL.md
```

Within user/workspace tiers, `.agents/skills` has precedence over `.gemini`.
Activation prompts for user consent and grants access to the skill directory.

```bash
gemini skills install https://github.com/OWNER/repo-dive.git \
  --path skills/wiki --scope user
gemini skills list --all
gemini skills uninstall wiki --scope user
```

`--scope` supports `user` (default) and `workspace`; `--consent` skips the
confirmation. `/skills link <path>` and `gemini skills link .` support local
development.

### Verified Gemini extension packaging

```text
repo-dive/
├── gemini-extension.json
└── skills/
    └── wiki/
        └── SKILL.md
```

Each extension root requires `gemini-extension.json`; `name` and `version` are
the basic identity fields. Skills under `skills/` are automatically discovered,
so no skill path declaration is required.

```json
{
  "name": "repo-dive",
  "version": "1.0.0",
  "description": "Evidence-grounded repository Wiki workflow"
}
```

```bash
gemini extensions install https://github.com/OWNER/repo-dive --ref v1.0.0
gemini extensions link ./repo-dive
gemini extensions update repo-dive
gemini extensions uninstall repo-dive
```

Installed extensions are copied under `~/.gemini/extensions`; changes require
update/reinstall and session restart, while `link` creates a development
symlink.

Sources:

- [Gemini CLI Agent Skills](https://geminicli.com/docs/cli/skills/)
- [Creating Gemini skills](https://geminicli.com/docs/cli/creating-skills/)
- [Gemini extensions overview](https://geminicli.com/docs/extensions/)
- [Build Gemini extensions](https://geminicli.com/docs/extensions/writing-extensions/)
- [Gemini extension reference](https://geminicli.com/docs/extensions/reference/)

## GitHub Copilot coding agent and CLI

### Verified standalone skill layout and installation

Copilot cloud agent, code review, Copilot CLI/app, and agent modes support Agent
Skills. Project and personal paths are:

```text
.github/skills/wiki/SKILL.md
.claude/skills/wiki/SKILL.md
.agents/skills/wiki/SKILL.md
~/.copilot/skills/wiki/SKILL.md
~/.agents/skills/wiki/SKILL.md
```

GitHub CLI 2.90.0+ offers public-preview distribution:

```bash
gh skill preview OWNER/repo-dive wiki
gh skill install OWNER/repo-dive wiki
gh skill install OWNER/repo-dive wiki --agent github-copilot --scope project
gh skill install OWNER/repo-dive wiki --pin v1.0.0
gh skill publish --dry-run
```

`gh skill publish --dry-run` validates Agent Skills naming, directory matching,
required frontmatter, and that `allowed-tools` is a string. Publishing creates
a GitHub release and can add the `agent-skills` repository topic. The CLI
injects provenance metadata into installed frontmatter for updates.

Copilot CLI also supports:

```bash
copilot skill add <FILE|URL|DIRECTORY>
# in-session verification
/skills reload
/skills info wiki
```

For cloud agent discovery, the skill must be in one of the project paths in the
repository. A personal path on a developer machine is not part of a cloud clone.

### Verified Copilot plugin layout and manifest

```text
repo-dive/
├── plugin.json
└── skills/
    └── wiki/
        └── SKILL.md
```

Root `plugin.json` is required by the documented simple layout; only `name` is
required, and `skills/` is the default component directory. Copilot additionally
checks `.plugin/plugin.json`, `.github/plugin/plugin.json`, and
`.claude-plugin/plugin.json`, so a Claude plugin manifest can also be consumed.

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "repo-dive",
  "version": "1.0.0",
  "description": "Evidence-grounded repository Wiki workflow"
}
```

Copilot can direct-install a plugin from GitHub, a Git URL, a repository
subdirectory, or local path:

```bash
copilot plugin install OWNER/repo-dive
copilot plugin install OWNER/repo-dive:PATH/TO/PLUGIN
copilot plugin install ./repo-dive
copilot plugin list
copilot plugin uninstall repo-dive
```

Marketplace catalogs live at `.github/plugin/marketplace.json`; Copilot also
accepts `.claude-plugin/marketplace.json`, enabling Claude marketplace catalog
reuse. Marketplace installation is:

```bash
copilot plugin marketplace add OWNER/REPO
copilot plugin install repo-dive@MARKETPLACE-NAME
```

Copilot plugin skills lose to same-named project or personal skills (first
found wins). This differs from Claude's plugin namespacing and must be tested
when a `wiki` skill already exists.

Sources:

- [About Copilot Agent Skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)
- [Adding Agent Skills for Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)
- [Adding Agent Skills for Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)
- [GitHub CLI `gh skill install`](https://cli.github.com/manual/gh_skill_install)
- [About Copilot plugins](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-cli-plugins)
- [Create a Copilot plugin](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating)
- [Install Copilot plugins](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing)
- [Copilot plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)

## Cross-platform manifest conflict summary

| File | Native reader(s) verified | Key point |
|---|---|---|
| `skills/wiki/SKILL.md` | All five when installed/bundled in the host's expected place | Authoritative portable content |
| `plugin.json` | GitHub Copilot; Agent Plugins conformant clients | Portable Agent Plugins v1 entry point; not verified as native entry point for the other four |
| `.claude-plugin/plugin.json` | Claude Code; GitHub Copilot; OpenAI submission importer | Claude native; can reduce Copilot duplication |
| `.codex-plugin/plugin.json` | ChatGPT/Codex plugin system | OpenAI native; distinct path and schema |
| `gemini-extension.json` | Gemini CLI | Gemini native; distinct schema |
| OpenCode npm `package.json` / `opencode.json` | OpenCode runtime plugins | Not a skills-only package manifest |

## Related Specs

- No `.trellis/spec/**/*.md` files were present when searched.

## Caveats / Not Found

- No official evidence showed OpenCode loading skills bundled in an npm runtime
  plugin automatically.
- No official evidence showed Claude Code, Codex, OpenCode, or Gemini CLI
  treating Agent Plugins v1 root `plugin.json` as a complete replacement for
  their native plugin/extension manifest.
- Gemini's site currently displays a notice that unpaid-tier Gemini CLI would
  be replaced by Antigravity CLI on 2026-06-18, yet it maintains current Gemini
  CLI skill/extension documentation updated in April-May 2026. Supported product
  editions and migration status must be checked when testing.
