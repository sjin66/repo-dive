# Research: Minimal repo-dive package architecture and test matrix

- **Query**: Provide a minimal evidence-based architecture and testing matrix for a package named `repo-dive` exposing `skills/wiki/SKILL.md`, while clearly separating facts from assumptions.
- **Scope**: mixed
- **Date**: 2026-08-29

## Findings

### Files Found

| File Path | Description |
|---|---|
| `.trellis/tasks/08-29-repo-dive-agent-plugin/prd.md` | Requirements and acceptance criteria for the new package. |
| `.agents/skills/repo-dive/SKILL.md` | Existing repository-local Wiki orchestration skill; source behavior to preserve. |
| `.agents/skills/repo-dive/references/workflow-contract.md` | Existing JSON, command sequence, exit-code recovery, and artifact contract. |
| `pyproject.toml` | Python distribution is already named `repo-dive` and exposes the `repo-dive` executable. |

### Verified internal constraints

- The requested Agent package is named `repo-dive` and initially exposes
  `wiki` (`prd.md:24-30`).
- It must not imply that plugin installation also installs the Python CLI
  (`prd.md:19-22`) and must report a missing executable rather than silently
  installing it (`prd.md:55-56`).
- Shared skill content must have one authoritative source (`prd.md:38-39`).
- Platform layouts/install mappings require clean-workspace checks
  (`prd.md:52-60`).
- The existing skill already codifies the actual deterministic/model boundary
  (`.agents/skills/repo-dive/SKILL.md:8-12`), preflight
  (`.agents/skills/repo-dive/SKILL.md:23-34`), sequential resumable workflow
  (`.agents/skills/repo-dive/SKILL.md:36-64`), and completion checks
  (`.agents/skills/repo-dive/SKILL.md:81-90`).
- The detailed reference documents exact page input and exit behavior
  (`.agents/skills/repo-dive/references/workflow-contract.md:38-93`).
- The executable is separately installed from the Python project:
  `pyproject.toml:5-17` names the distribution and `pyproject.toml:30-31`
  defines the console script.

## Minimal recommended architecture

This is an evidence-based compatibility architecture, not a claim that every
listed file is mandatory on every host.

```text
repo-dive/                         # one distributable plugin repository/root
├── plugin.json                    # Agent Plugins v1 + native Copilot
├── .claude-plugin/
│   ├── plugin.json                # Claude native manifest
│   └── marketplace.json           # optional Claude/Copilot catalog
├── .codex-plugin/
│   └── plugin.json                # OpenAI native manifest
├── gemini-extension.json          # Gemini native manifest
├── skills/
│   └── wiki/
│       ├── SKILL.md                # sole authoritative skill instructions
│       └── references/
│           └── workflow-contract.md
├── README.md
├── LICENSE
└── tests/                         # package/layout/install contract tests
```

Rationale tied to verified contracts:

1. `skills/wiki/SKILL.md` is simultaneously the Agent Skills standard layout,
   the Agent Plugins fixed layout, and the default skills component layout for
   Claude, OpenAI, Gemini, and Copilot packages. skills.sh and `gh skill` also
   discover it directly.
2. A root standard `plugin.json` makes the package a valid Agent Plugins v1
   package and directly installable by Copilot. It does not replace the three
   verified vendor manifests.
3. `.claude-plugin/plugin.json` is read by Claude and Copilot and is accepted by
   OpenAI's Claude-plugin import path. `.claude-plugin/marketplace.json` is also
   accepted by both Claude and Copilot.
4. `.codex-plugin/plugin.json` and `gemini-extension.json` are thin identity
   adapters that point at or conventionally discover the same `skills/` tree;
   no skill body duplication is needed.
5. OpenCode needs no additional manifest for a skills-only package when
   skills.sh installs `wiki` to `.agents/skills/wiki` or its native OpenCode
   path. Adding an OpenCode JS plugin would introduce a different capability
   type not required for this instruction-only workflow.

### Minimal manifest requirements by target

| Target route | Required package metadata | Shared skill path |
|---|---|---|
| skills.sh / Vercel CLI | No package manifest; valid Agent Skills frontmatter | `skills/wiki/SKILL.md` |
| Agent Plugins v1 / Copilot direct plugin | root `plugin.json` with canonical `$schema`, `name: repo-dive` | fixed `skills/wiki/SKILL.md` |
| Claude native plugin | `.claude-plugin/plugin.json`, `name` required | default `skills/wiki/SKILL.md` |
| OpenAI native plugin | `.codex-plugin/plugin.json` with identity and `skills: ./skills/` | `skills/wiki/SKILL.md` |
| Gemini native extension | `gemini-extension.json` with at least identity/version | auto-discovers `skills/wiki/SKILL.md` |
| OpenCode direct skill | no plugin manifest | installed into `.agents/skills/wiki/SKILL.md` or another documented path |
| GitHub `gh skill` | no package manifest | discovers `skills/wiki/SKILL.md` |

## Minimal testing matrix

Tests below distinguish **static contract tests** (fully automatable without
accounts/models) from **host smoke tests** (require pinned installed clients).

### A. Portable package/static checks

| Check | Expected evidence |
|---|---|
| Agent Skills validation | `skills-ref validate skills/wiki` exits 0; name exactly matches `wiki`; only standard frontmatter is used. |
| Resource closure | Every relative file reference in `SKILL.md` exists under `skills/wiki/`; no `../` escape or dependency on repository-local `.agents/skills/repo-dive`. |
| Agent Plugins schema | root `plugin.json` validates against `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`; immediate `skills/wiki/SKILL.md` exists. |
| Claude validation | `claude plugin validate <package> --strict` exits 0. |
| GitHub validation | `gh skill publish --dry-run` exits 0 without publishing. |
| Vercel discovery | `npx skills add <local-package> --list` lists exactly `wiki`; test both normal and `--copy` installation modes where symlinks matter. |
| Identity consistency | All plugin/extension manifests identify `repo-dive`; all skill surfaces identify `wiki`; versions match where declared. |
| Prerequisite boundary | Package contains no Python wheel/vendor environment and docs/skill explicitly require `command -v repo-dive` without installing it. |

### B. Clean-workspace install/discovery checks

| Host / route | Installation in isolated temp Git repo | Discovery assertion | Uninstall/rollback assertion |
|---|---|---|---|
| Claude, skills.sh | `npx skills add <source> --skill wiki -a claude-code -y` | `.claude/skills/wiki/SKILL.md` resolves; fresh `claude` lists/invokes `/wiki`. | `npx skills remove wiki -a claude-code -y`; no unrelated files changed. |
| Claude native plugin | `claude --plugin-dir <package>` for dev; marketplace add/install for packaged path | `/repo-dive:wiki` appears and plugin details list one skill. | `claude plugin uninstall repo-dive@<marketplace> --scope <scope>`. |
| Codex, skills.sh | project install with `-a codex` | `.agents/skills/wiki/SKILL.md`; fresh Codex `/skills` or `$wiki` sees it. | `npx skills remove wiki -a codex -y`. |
| Codex native plugin | add local/repo marketplace; install through documented ChatGPT/Codex plugin surface | plugin lists one `wiki` skill and its references. | disable/remove plugin and verify skill disappears. |
| OpenCode, skills.sh | project install with `-a opencode` | `.agents/skills/wiki/SKILL.md`; OpenCode's available-skills tool lists `wiki`. | remove via skills CLI; fresh session no longer lists it. |
| Gemini standalone | `gemini skills install <source> --path skills/wiki --scope workspace --consent` | `gemini skills list` reports `wiki`; activation asks consent when `--consent` was not used for execution. | `gemini skills uninstall wiki --scope workspace`. |
| Gemini extension | `gemini extensions install <source> --ref <pin> --consent` | extension list includes `repo-dive`; `/skills list` includes `wiki`. | `gemini extensions uninstall repo-dive`. |
| Copilot skill | `gh skill install OWNER/repo-dive wiki --agent github-copilot --scope project` | `.agents/skills/wiki` or host-selected project path exists; Copilot `/skills info wiki` succeeds. | remove skill; confirm project tree restoration. |
| Copilot plugin | `copilot plugin install OWNER/repo-dive` | `copilot plugin list` has `repo-dive`; `/skills list` has `wiki`. | `copilot plugin uninstall repo-dive`. |
| Multi-host one-command | skills.sh command targeting all five agents | destination mapping is correct; canonical source/symlink behavior does not produce divergent file bodies. | remove all; only installer metadata/canonical cache allowed by documented behavior remains. |

### C. Behavioral skill checks, once per host

Use a tiny fixture repository and two executable states:

1. **CLI absent:** invoke/trigger `wiki`; assert it stops at preflight, clearly
   states the `repo-dive` CLI prerequisite, and performs no install or clone.
2. **CLI stub present:** put a deterministic stub named `repo-dive` first on
   `PATH`; assert calls begin with `--version`/`wiki --help`, then use JSON mode,
   treat stdout as one JSON document, and handle exit codes 2/3/4 as documented.
3. **Real CLI present:** execute the complete fixture Wiki sequence and assert
   `<fixture>/.repo-dive/wiki.md` is produced only after successful build.
4. **Source URL request:** assert the skill does not clone without separate
   authorization.
5. **Dirty Git tree:** assert unrelated changes remain untouched.
6. **Trigger tests:** one positive Wiki-generation prompt, one explicit host
   invocation where supported, and negative prompts that should not activate
   the skill.
7. **Name collision:** preinstall a different `wiki` skill and record each
   host's documented precedence/namespacing outcome rather than assuming the
   package wins.

### D. Versions/platforms to record

For every smoke-test artifact, record OS, architecture, package source/ref or
SHA, Node/npm version (skills.sh), and exact versions of `claude`, `codex`,
`opencode`, `gemini`, `copilot`, and `gh`. Native conventions changed rapidly
in 2026; a passing test without these versions is not reproducible evidence.

## Verified compatibility boundaries

- Installing the Agent package does not install the Python executable. This is
  both a product requirement and consistent with every reviewed skill package
  convention.
- The portable skill must not depend on Claude-only frontmatter or body
  expansion. Host-specific invocation instructions belong in host docs, not in
  the shared operational contract unless phrased conditionally.
- Plugin caches copy packages. References outside the plugin root are unsafe;
  the existing repository-local reference must be copied under the new
  `skills/wiki/references/` authoritative tree or otherwise generated from one
  source during packaging.
- A single checkout can contain all thin manifests without duplicating the
  skill. However, native registries remain separate and publication/review on
  one does not confer approval on another.
- OpenCode runtime plugins are not needed to install a skill and cannot be
  treated as equivalent to Claude/Codex/Gemini/Copilot skill bundles.

## Assumptions requiring implementation-time verification

1. **One repository root as all native package roots:** the documented formats
   can coexist, but each host must be smoke-tested against the same physical
   directory and release archive.
2. **Catalog self-source:** if a marketplace entry points to the repository root
   containing the catalog itself, validate that each host accepts that source;
   otherwise a `plugins/repo-dive/` package subdirectory may be required.
3. **Codex plugin CLI UX:** official docs clearly define catalog commands and
   ChatGPT desktop installation, but exact headless plugin-install support must
   be checked in the pinned Codex build.
4. **Global third-party Codex path:** skills.sh currently documents
   `~/.codex/skills`, while OpenAI documents `~/.agents/skills`; do not declare
   global Codex support until this is tested or the installer mapping changes.
5. **Gemini product transition:** the Gemini documentation's Antigravity
   transition notice may affect which user tiers can execute the matrix.

## External References

- [Agent Skills specification](https://agentskills.io/specification) — portable skill contract.
- [Agent Plugins specification](https://agent-plugins.org/specification) — portable plugin contract.
- [skills.sh CLI source documentation](https://github.com/vercel-labs/skills) — cross-host installation mappings.
- [Claude plugin reference](https://code.claude.com/docs/en/plugins-reference) — Claude package validation/layout.
- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins.md) — Codex/ChatGPT package and marketplace layout.
- [OpenCode Agent Skills](https://opencode.ai/docs/skills/) — OpenCode discovery paths.
- [Gemini extension reference](https://geminicli.com/docs/extensions/reference/) — Gemini extension install/layout.
- [Copilot plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference) — direct installs, manifests, and marketplace compatibility.

## Related Specs

- No `.trellis/spec/**/*.md` files were present when searched.

## Caveats / Not Found

- This research did not execute vendor CLIs or create product code; the matrix
  identifies the clean-environment verification needed by the acceptance
  criteria.
- Publishing to external registries is out of scope in the active PRD; all
  registry notes describe available conventions, not an instruction to publish.
