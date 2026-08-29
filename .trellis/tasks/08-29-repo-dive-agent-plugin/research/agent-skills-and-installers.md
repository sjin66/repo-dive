# Research: Agent Skills standard, skills.sh, and cross-host installers

- **Query**: Determine the authoritative Agent Skills packaging rules and whether a repository package named `repo-dive` with `skills/wiki/SKILL.md` can be installed through skills.sh or an equivalent across Claude Code, Codex CLI, OpenCode, Gemini CLI, and GitHub Copilot.
- **Scope**: external
- **Date**: 2026-08-29

## Findings

### Verified facts: Agent Skills open standard

The normative unit is a **skill directory**, not a repository, registry package,
or plugin. A valid skill has this minimum shape:

```text
wiki/
└── SKILL.md
```

`SKILL.md` must start with YAML frontmatter and then Markdown. The required
frontmatter fields are:

```yaml
---
name: wiki
description: What the skill does and when an agent should use it.
---
```

The current specification imposes these key constraints:

- `name` is 1-64 characters, lowercase `a-z`, digits, and single hyphens only;
  it may not begin/end with a hyphen or contain `--`, and it must match its
  parent directory (`wiki`).
- `description` is non-empty and at most 1,024 characters.
- Standard optional fields are `license`, `compatibility`, `metadata`, and the
  experimental string field `allowed-tools`.
- `scripts/`, `references/`, and `assets/` are conventional optional resource
  directories; other files/directories are permitted.
- Relative links in `SKILL.md` are resolved from the skill root.
- Progressive disclosure is part of the model: clients initially expose
  `name` and `description`, load the complete `SKILL.md` on activation, and
  access resources only when required.
- The standard recommends keeping `SKILL.md` below 500 lines and about 5,000
  tokens and keeping reference chains shallow.
- The reference validator is `skills-ref validate ./path/to/wiki`.

Authoritative sources:

- [Agent Skills specification](https://agentskills.io/specification)
- [Agent Skills overview](https://agentskills.io/home)
- [Reference implementation and validator](https://github.com/agentskills/agentskills/tree/main/skills-ref)

The Agent Skills site identifies Claude Code, ChatGPT/Codex, OpenCode, Gemini
CLI, and GitHub Copilot as supporting clients. That verifies format adoption,
but **does not standardize repository discovery, installation, registries,
invocation syntax, permissions, or updates**. Those remain host-specific.

### Verified facts: Agent Plugins open standard (adjacent, newer standard)

Agent Plugins v1.0.0 is a separate, published, vendor-neutral package standard.
Its portable minimum is:

```text
repo-dive/
├── plugin.json
└── skills/
    └── wiki/
        └── SKILL.md
```

The root `plugin.json` must include:

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "repo-dive"
}
```

The standard discovers only immediate skill children at
`skills/<name>/SKILL.md`. Agent Plugins v1 standardizes skills and optional
`mcp.json`; hooks, agents, commands, LSP, installation sources, registries,
permissions, and update UX are deliberately outside its portable core.
Client-specific behavior belongs under reverse-domain extension namespaces.

The initial steering committee includes maintainers from Amazon, Cursor,
Microsoft, OpenAI, and Vercel. GitHub Copilot explicitly documents support for
opting into this standard with the canonical `$schema`. The reviewed official
Claude Code, Codex, OpenCode, and Gemini CLI documentation did **not** establish
that each of those products natively accepts this root `plugin.json` as its
plugin entry point. It therefore cannot presently replace all vendor manifests.

Sources:

- [Agent Plugins overview](https://agent-plugins.org/)
- [Agent Plugins v1.0.0 specification](https://agent-plugins.org/specification)
- [Build an Agent Plugin](https://agent-plugins.org/plugin-authors/build-an-agent-plugin)
- [GitHub Copilot plugin reference: Open Plugin Spec support](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference#open-plugin-spec-support)

### Verified facts: skills.sh / Vercel `skills` CLI

`skills.sh` is a directory/leaderboard powered by the open-source
[`vercel-labs/skills`](https://github.com/vercel-labs/skills) CLI. It is not the
Agent Skills specification itself and is not an official installer owned by
all five host vendors.

For a public GitHub repository `OWNER/repo-dive` containing
`skills/wiki/SKILL.md`, the CLI's documented discovery rules find `wiki`
without any package manifest. Commands include:

```bash
# Inspect repository discovery without installing
npx skills add OWNER/repo-dive --list

# Install only wiki and choose/detect a host interactively
npx skills add OWNER/repo-dive --skill wiki

# Deterministic project-scope installs for the five requested hosts
npx skills add OWNER/repo-dive --skill wiki \
  -a claude-code -a codex -a opencode -a gemini-cli -a github-copilot -y

# User-scope example
npx skills add OWNER/repo-dive --skill wiki -g -a claude-code -y
```

The CLI also accepts a GitHub tree URL directly, arbitrary Git/GitLab URLs,
local directories, a direct `SKILL.md`, and bounded archives. By default it
installs at project scope, keeps a canonical skill copy, and symlinks target
host locations; `--copy` requests independent copies. `npx skills update`
updates tracked installs. It collects installation telemetry unless
`DISABLE_TELEMETRY=1` or `DO_NOT_TRACK=1` is set.

For the requested hosts, its current target mapping is:

| Host | `--agent` | Project target | Global target used by installer |
|---|---|---|---|
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `codex` | `.agents/skills/` | `~/.codex/skills/` |
| OpenCode | `opencode` | `.agents/skills/` | `~/.config/opencode/skills/` |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` |
| GitHub Copilot | `github-copilot` | `.agents/skills/` | `~/.copilot/skills/` |

Important compatibility detail: Codex's official current user location is
`~/.agents/skills`, while the Vercel installer table says `~/.codex/skills`.
The project mapping `.agents/skills` is aligned. Therefore project-scope Codex
installation is verified by both sources, while **global Codex installation
through this third-party CLI requires an actual smoke test against the pinned
CLI/host versions** rather than relying solely on documentation.

Repository discovery is broad. The CLI finds a root `SKILL.md`, standard
`skills/` catalogs (up to three levels), many host-specific skill folders, and
Claude plugin manifest-declared skill paths. Thus `skills/wiki/SKILL.md` is the
least host-specific repository layout it supports.

Sources:

- [skills.sh documentation](https://skills.sh/docs)
- [skills.sh CLI docs](https://skills.sh/docs/cli)
- [vercel-labs/skills README and definitive current mapping](https://github.com/vercel-labs/skills#supported-agents)
- [vercel-labs/skills discovery rules](https://github.com/vercel-labs/skills#skill-discovery)

### Verified equivalents not requiring skills.sh

| Host | Native/equivalent repository install for `skills/wiki/SKILL.md` |
|---|---|
| Claude Code | No official one-command Git skill installer was documented. A plain skill must be copied/symlinked into `.claude/skills/wiki` or `~/.claude/skills/wiki`; native distributable installation uses a Claude plugin marketplace instead. |
| Codex CLI | The built-in `$skill-installer` can download skills from `openai/skills` or other repositories; exact repository selection is prompt-driven. Native distributable installation uses an OpenAI plugin/local marketplace. |
| OpenCode | No official skill registry/install command was documented. Copy/symlink into one of its discovery paths, or use the third-party `skills` CLI. OpenCode's native “plugins” are JavaScript/TypeScript runtime modules and are not skill bundles. |
| Gemini CLI | `gemini skills install https://github.com/OWNER/repo-dive.git --path skills/wiki --consent` (omit `--consent` for review prompt); alternatively install a Gemini extension containing the same skill. |
| GitHub Copilot | `gh skill install OWNER/repo-dive wiki` (GitHub CLI 2.90.0+, public preview), with `--agent`/`--scope` as needed; `copilot skill add <FILE|URL|DIRECTORY>` is another supported route. |

### Answer to the package-layout question

**Verified conclusion:** yes, a repository named `repo-dive` with
`skills/wiki/SKILL.md` is a valid source package for `skills.sh` and is also a
native source shape for `gh skill`, Gemini's repository skill installer, and
the skills portions of Claude, Codex, Gemini, and Copilot plugin packages.

**Qualification:** the repository name does not make it an installable native
plugin on every host. Native plugin installation additionally requires
host-specific manifests/catalogs, except where direct skill installation is
used. OpenCode has no documented skills-only plugin manifest. A `SKILL.md`
alone also cannot install the separate Python `repo-dive` executable.

## Compatibility conflicts

1. **Standard vs host extensions:** portable frontmatter should stay within the
   six Agent Skills fields. Claude-only keys such as `context`,
   `disable-model-invocation`, `argument-hint`, or shell interpolation are not
   portable; Anthropic documents hard errors when such skills are uploaded to
   standard-only Claude surfaces.
2. **`allowed-tools`:** it is experimental in Agent Skills and host semantics
   differ. OpenCode's official skills page recognizes only five fields and
   ignores unknown fields; its omission of `allowed-tools` means it should not
   be relied upon there. Gemini's docs likewise do not promise this field.
3. **Invocation names differ:** plain skills are generally `wiki`, but Claude
   plugin skills are namespaced (`repo-dive:wiki`); Codex uses `$wiki` or a
   skill picker; Copilot CLI supports `/wiki`; OpenCode activates through its
   `skill` tool; Gemini activates with consent.
4. **Symlinks:** Claude, Codex, and the third-party installer document symlink
   support, but copied/cached native plugins may not preserve references outside
   the package. Every referenced resource must remain inside `wiki/`.
5. **Security/trust:** all installers warn that skills may contain executable
   scripts or prompt injection. A portable package must not assume shell tools
   are pre-approved.

## Related Specs

- No `.trellis/spec/**/*.md` files were present when searched.
- `.trellis/tasks/08-29-repo-dive-agent-plugin/prd.md:24-45` defines the local
  cross-platform, single-authoritative-source, documentation requirements.

## Caveats / Not Found

- skills.sh is an ecosystem installer, not a universal vendor-backed plugin
  registry or a guarantee that every host's latest version will load every
  installed path.
- No common native installation command shared by all five platforms was found.
- Native plugin standards are actively changing as of the research date;
  documentation and exact CLI versions must be pinned in test evidence.
