# Repo Dive Agent Plugin Implementation Plan

## 1. Portable Package

- [x] Move the existing Wiki skill behavior into the authoritative
  `skills/wiki/` tree and rename its portable identity to `wiki`.
- [x] Keep the workflow reference self-contained under
  `skills/wiki/references/` and verify every relative link.
- [x] Remove the obsolete repository-local duplicate so only one committed
  operational skill source remains.

Validation:

```bash
python3 -m pytest tests/unit/test_agent_plugin.py -q
```

Rollback point: the portable skill tree can be reverted independently before
adding any platform manifest.

## 2. Platform Metadata

- [x] Add Agent Plugins v1 `plugin.json` for package identity and Copilot.
- [x] Add `.claude-plugin/plugin.json` for Claude Code.
- [x] Add `.codex-plugin/plugin.json` pointing to `./skills/` for Codex.
- [x] Add `gemini-extension.json` for Gemini CLI.
- [x] Keep every adapter on package name `repo-dive` and one version.
- [x] Do not add an OpenCode JS runtime plugin.

Validation:

```bash
python3 -m pytest tests/unit/test_agent_plugin.py -q
```

Optional when installed:

```bash
claude plugin validate .
gh skill publish --dry-run
npx skills add . --list
```

Rollback point: remove only the failing platform adapter; the portable skill
remains independently installable.

## 3. Contract Tests

- [x] Add package tests for required files, portable frontmatter, identity and
  version consistency, resource closure, and forbidden duplicate skill roots.
- [x] Assert the skill preserves the CLI/model boundary and references the
  implemented JSON Wiki stages and output path.
- [x] Keep external vendor CLIs optional so default tests remain offline.

Validation:

```bash
make test-unit
```

## 4. Documentation

- [x] Add matched English and Simplified Chinese plugin installation guides.
- [x] Document one project-scoped multi-Agent installation command and each
  official native route that can consume the package.
- [x] Document platform-specific discovery/invocation, CLI prerequisite,
  update/uninstall behavior, limitations, and version-sensitive caveats.
- [x] Link the paired guides from both README files without changing the CLI
  product boundary.

Validation:

```bash
python3 scripts/check_repo_contract.py
```

## 5. Final Verification

- [x] Review the diff for accidental edits to the Python CLI or existing user
  work.
- [x] Run all required repository quality gates. `make check` remains blocked
  only by unrelated `.trellis` formatting failures recorded in `prd.md`.
- [x] Record any unavailable vendor smoke checks as residual verification gaps,
  including exact installed client versions for checks that run.

```bash
make check
make test-all
git diff --check
```

## 6. Direct CLI Initialization

- [x] Add failing tests for bare TTY multi-selection, repeatable `--agent`, JSON
  mode, non-TTY validation, and invalid Agent values.
- [x] Add an installer service that maps selected Agents to deduplicated project
  destinations and validates all conflicts before writing.
- [x] Implement idempotent install, conflict preservation, and explicit
  `--force` replacement without invoking external processes or the network.
- [x] Register `init` through the existing typed `Command` boundary and preserve
  exit codes, JSON stdout isolation, and stderr diagnostics.
- [x] Force-include the authoritative root `skills/wiki` tree as wheel resources
  and load it through `importlib.resources`.
- [x] Extend package smoke coverage to install a built wheel and run
  non-interactive `repo-dive init` in a temporary Git repository.
- [x] Update matched English and Simplified Chinese docs so `repo-dive init` is
  the primary installation route; retain native and `npx skills` alternatives.

Validation:

```bash
python3 -m pytest tests/unit/test_agent_plugin.py tests/unit/test_init.py -q
python3 -m pytest tests/integration/test_init_command.py -q
make check
make test-all
git diff --check
```

Rollback point: remove the `init` command/service and Hatch resource mapping.
Do not delete skills already installed in user repositories.
