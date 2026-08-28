# Repo Dive CLI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a testable pure-Python CLI project with authoritative agent instructions, bilingual engineering documentation, shared local/CI verification commands, and evaluation scaffolding.

**Architecture:** The foundation provides a standard `src/` package and a dependency-free `argparse` CLI shell while keeping all future repository-analysis behavior outside this delivery. Root `AGENTS.md` is authoritative; tool-specific files reference it. Make targets are the only supported verification entry points and GitHub Actions calls those same targets.

**Tech Stack:** Python 3.11+, `argparse`, Hatchling, pytest, Ruff, mypy, GNU Make, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-28-repo-dive-cli-foundation-design.md`

## Global Constraints

- The project is pure Python and supports Python 3.11 or newer.
- The foundation must not implement scanning, parsing, indexing, retrieval, context assembly, or wiki generation.
- The CLI must not invoke a generative model.
- Root `AGENTS.md` is the single authoritative agent contract.
- Agent/harness documents are English; user/developer CLI documents have English and Simplified Chinese counterparts.
- The shared verification entry points are exactly `make setup`, `make check`, `make test-unit`, and `make test-all`.
- Future generated wiki output is fixed at `<repository>/.repo-dive/wiki.md` with `wiki.json`, `metadata.json`, and `index/` beside it.

---

### Task 1: Package and CLI Shell

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `src/repo_dive/__init__.py`
- Create: `src/repo_dive/__main__.py`
- Create: `src/repo_dive/cli.py`
- Create: `tests/unit/test_cli.py`
- Create: `tests/integration/.gitkeep`
- Create: `tests/fixtures/.gitkeep`

**Interfaces:**
- Consumes: no earlier task interfaces.
- Produces: `repo_dive.__version__: str`, `repo_dive.cli.build_parser() -> argparse.ArgumentParser`, `repo_dive.cli.main(argv: Sequence[str] | None = None) -> int`, and console command `repo-dive`.

- [ ] **Step 1: Write CLI tests**

Create `tests/unit/test_cli.py` with tests that call `main(["--version"])` and `main(["--help"])`, asserting exit behavior and output without spawning a subprocess. Use `pytest.raises(SystemExit)` only for argparse help because version returns `0` directly.

```python
import pytest

from repo_dive import __version__
from repo_dive.cli import main


def test_version_prints_stable_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"repo-dive {__version__}"


def test_help_describes_agent_friendly_cli(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "local repository evidence" in output
```

- [ ] **Step 2: Run the focused tests and confirm the expected import failure**

Run: `python3 -m pytest tests/unit/test_cli.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'repo_dive'`.

- [ ] **Step 3: Add packaging and the minimal CLI implementation**

Configure Hatchling with package discovery under `src`, project name `repo-dive`, version `0.1.0`, Python requirement `>=3.11`, no runtime dependencies, a `dev` extra containing pytest/Ruff/mypy, and this console script:

```toml
[project.scripts]
repo-dive = "repo_dive.cli:entrypoint"
```

Implement `build_parser`, `main`, and `entrypoint` using `argparse`. `--version` must be handled by `main` so it returns `0`; `entrypoint` converts the return value to `SystemExit` for the console script. Do not add functional subcommands.

- [ ] **Step 4: Install and run the focused tests**

Run: `python3 -m pip install -e ".[dev]"`

Run: `python3 -m pytest tests/unit/test_cli.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Smoke-test the installed command**

Run: `repo-dive --version`

Expected: `repo-dive 0.1.0` and exit code `0`.

- [ ] **Step 6: Commit the package shell**

```bash
git add pyproject.toml .python-version .gitignore src tests
git commit -m "chore: scaffold repo-dive CLI package"
```

### Task 2: Agent Authority and Bilingual Documentation

**Files:**
- Create: `AGENTS.md`
- Create: `.github/copilot-instructions.md`
- Create: `CLAUDE.md`
- Create: `GEMINI.md`
- Create: `README.md`
- Create: `README.zh-CN.md`
- Create: `docs/en/architecture.md`
- Create: `docs/en/cli-contract.md`
- Create: `docs/en/wiki-workflow.md`
- Create: `docs/en/development.md`
- Create: `docs/zh-CN/architecture.md`
- Create: `docs/zh-CN/cli-contract.md`
- Create: `docs/zh-CN/wiki-workflow.md`
- Create: `docs/zh-CN/development.md`
- Create: `tests/unit/test_documentation_contract.py`

**Interfaces:**
- Consumes: the command and package names from Task 1.
- Produces: the repository-wide implementation rules and paired documentation paths relied on by all later plans.

- [ ] **Step 1: Write documentation-contract tests**

Create a parametrized test that asserts every English engineering document has a Simplified Chinese counterpart. Add assertions that `AGENTS.md` contains `make check`, `make test-unit`, `make test-all`, `.repo-dive/wiki.md`, and the rule that generative models are not called implicitly. Assert each compatibility file references `AGENTS.md` and remains below 20 non-empty lines.

- [ ] **Step 2: Run the documentation tests and confirm missing-file failures**

Run: `python3 -m pytest tests/unit/test_documentation_contract.py -q`

Expected: failures identify the absent authority and paired documentation files.

- [ ] **Step 3: Write the root authority and compatibility files**

Write `AGENTS.md` in English with these enforceable sections: product boundary, source layout, dependency direction, process I/O contract, `.repo-dive/` artifact contract, testing rules, documentation synchronization, security/path handling, and required verification commands. `.github/copilot-instructions.md`, `CLAUDE.md`, and `GEMINI.md` must contain only a brief instruction to load and follow `AGENTS.md`; they must not duplicate policy.

- [ ] **Step 4: Write paired user and engineering documentation**

Both READMEs must describe the Copilot-calls-CLI model, current foundation status, planned command workflow, stable wiki path, and development commands. Each English/Chinese document pair must contain the same headings and technical contracts:

- `architecture.md`: planned package boundaries and dependency rules.
- `cli-contract.md`: stdout/stderr, JSON, exit codes, non-interactive execution, and path/line conventions.
- `wiki-workflow.md`: DeepWiki-compatible structure/page/assembly workflow mediated by the calling agent.
- `development.md`: environment setup, Make targets, tests, documentation synchronization, and contribution checks.

- [ ] **Step 5: Run documentation and CLI tests**

Run: `python3 -m pytest tests/unit/test_documentation_contract.py tests/unit/test_cli.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the agent and documentation contracts**

```bash
git add AGENTS.md CLAUDE.md GEMINI.md .github README.md README.zh-CN.md docs tests/unit/test_documentation_contract.py
git commit -m "docs: define agent and CLI contracts"
```

### Task 3: Shared Harness, CI, and Evaluation Scaffold

**Files:**
- Create: `Makefile`
- Modify: `pyproject.toml`
- Create: `.github/workflows/ci.yml`
- Create: `evals/README.md`
- Create: `evals/cases/cli_contract.jsonl`
- Create: `tests/unit/test_eval_manifest.py`

**Interfaces:**
- Consumes: package metadata and CLI behavior from Task 1; contracts from Task 2.
- Produces: the four stable Make entry points and JSONL evaluation-case schema used by future retrieval work.

- [ ] **Step 1: Write evaluation-manifest tests**

Parse every non-empty line under `evals/cases/*.jsonl` as JSON. Require string fields `id`, `category`, `prompt`, and `expected_behavior`; require unique IDs; reject unknown top-level fields except optional `command` and `assertions`.

- [ ] **Step 2: Run the manifest test and confirm the missing-case failure**

Run: `python3 -m pytest tests/unit/test_eval_manifest.py -q`

Expected: failure states that no evaluation case files were found.

- [ ] **Step 3: Add the initial evaluation cases**

Create JSONL cases for `repo-dive --help`, `repo-dive --version`, JSON stdout isolation, diagnostics on stderr, and the stable `.repo-dive/wiki.md` artifact path. Mark unimplemented functional behavior as a contract expectation rather than an executable command by omitting the optional `command` field.

- [ ] **Step 4: Configure static checks and Make targets**

Add Ruff settings for Python 3.11, 88-character formatting, and lint sets `E`, `F`, `I`, `UP`, `B`, and `SIM`. Add strict mypy configuration for `src/repo_dive` and typed tests. Implement Make targets:

```make
setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"

check:
	$(VENV_PYTHON) -m ruff check .
	$(VENV_PYTHON) -m ruff format --check .
	$(VENV_PYTHON) -m mypy src tests

test-unit:
	$(VENV_PYTHON) -m pytest tests/unit -q

test-all:
	$(VENV_PYTHON) -m pytest -q
```

Make must set `PYTHON ?= python3`, `VENV ?= .venv`, and derive `VENV_PYTHON` without using a home-directory variable.

- [ ] **Step 5: Add CI using only the shared entry points**

Create one GitHub Actions job on Ubuntu with Python 3.11 and 3.12. Each matrix run executes `make setup`, `make check`, and `make test-all`. Do not repeat Ruff, mypy, or pytest commands in YAML.

- [ ] **Step 6: Run the complete foundation harness**

Run: `make setup`

Run: `make check`

Run: `make test-unit`

Run: `make test-all`

Expected: every command exits `0`; the final pytest output reports all foundation tests passing.

- [ ] **Step 7: Verify CI delegates to Make**

Run: `rg -n "ruff|mypy|pytest" .github/workflows/ci.yml`

Expected: no matches.

Run: `rg -n "make (setup|check|test-all)" .github/workflows/ci.yml`

Expected: exactly three command matches in each matrix job definition.

- [ ] **Step 8: Commit the shared harness**

```bash
git add Makefile pyproject.toml .github/workflows/ci.yml evals tests/unit/test_eval_manifest.py
git commit -m "ci: add shared verification and eval harness"
```

### Task 4: Foundation Acceptance Review

**Files:**
- Review: all files introduced by Tasks 1-3.
- Modify only files that fail an acceptance check.

**Interfaces:**
- Consumes: all foundation deliverables.
- Produces: a verified baseline ready for the separate repository-scanning implementation plan.

- [ ] **Step 1: Check the implementation against the design spec**

Read the design spec line by line and verify each foundation deliverable and non-goal. Confirm no dependency or module for Tree-sitter, embeddings, FAISS, BM25, model providers, web frameworks, or MCP was introduced.

- [ ] **Step 2: Run fresh acceptance commands**

Run: `make check`

Run: `make test-all`

Run: `.venv/bin/repo-dive --help`

Run: `.venv/bin/repo-dive --version`

Expected: checks and tests exit `0`; help identifies the local repository evidence CLI; version prints `repo-dive 0.1.0`.

- [ ] **Step 3: Inspect repository status and tracked artifacts**

Run: `git status --short`

Run: `git ls-files`

Expected: only intentional source, documentation, harness, evaluation, and plan/spec files are tracked; `.venv/`, caches, and `.repo-dive/` are absent.

- [ ] **Step 4: Commit acceptance corrections only if required**

If acceptance checks required changes, stage the explicit corrected files and commit them with:

```bash
git commit -m "chore: align foundation acceptance contracts"
```

If no corrections were required, do not create an empty commit.

