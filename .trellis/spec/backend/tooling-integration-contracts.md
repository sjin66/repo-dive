# Tooling Integration Contracts

## Scenario: Repository-Owned Tooling Installation

### 1. Scope / Trigger

Apply this contract when repository instructions, hooks, or task workflows begin to
depend on generated development tooling. The committed tree must remain usable from a
fresh checkout without relying on files present only in one developer's clone.

### 2. Signatures

The repository-owned Trellis entry points are:

```bash
python3 ./.trellis/scripts/get_context.py --mode packages
python3 ./.trellis/scripts/get_context.py --mode phase --step <step>
python3 ./.trellis/scripts/task.py --help
.venv/bin/python -m ruff format --check --no-respect-gitignore .
.venv/bin/python -m ruff check --no-respect-gitignore .
```

Host-specific hooks and Skill payloads are local integrations unless their complete
installation is explicitly included in the committed asset set.

### 3. Contracts

- Every explicit required repository-owned path in committed instructions must
  resolve in the same commit. Optional Host examples, generated local paths,
  placeholders, and globs are exempt when the surrounding text identifies them as
  such.
- Committing `AGENTS.md` references to Trellis requires committing the referenced
  workflow, scripts, project configuration, and shared specifications.
- Local `.git/info/exclude` rules affect only one clone and cannot satisfy a
  fresh-checkout dependency.
- Ruff configuration must explicitly set `extend-exclude = [".trellis"]`. This is an
  exact boundary: generated Trellis runtime files are outside product formatting and
  lint ownership, while `src`, `tests`, and repository `scripts` remain checked.
- Host payload directories and `skills-lock.json` are committed together or remain
  local together; a lock file without its governed payload is incomplete.
- Staging uses an explicit allowlist so concurrent task and product changes cannot
  enter an infrastructure commit.

### 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| Committed instruction references a missing required repository-owned path | Block the commit and fix the reference or add the owned asset |
| Host payload enters a core-only commit | Block the commit and remove it from the staged allowlist |
| `skills-lock.json` is staged without governed Skills | Block the commit |
| Current worktree contains unrelated changes | Validate the staged snapshot in a clean temporary worktree |
| Ruff exclusion is missing, broader than `.trellis`, or relies on `.git/info/exclude` | Fail the repository contract |
| Default `python3` is older than 3.11 | Run `make setup PYTHON=/path/to/python3.11+` |
| `make check` or `make test-all` fails in the clean snapshot | Block completion |

### 5. Good / Base / Bad Cases

- Good: instructions, workflow, scripts, configuration, and referenced specs are
  committed together; clean-snapshot checks pass.
- Base: Host integrations remain local and are excluded from the commit while the
  repository-owned core is complete.
- Good: clean-snapshot Ruff checks use the repository-owned `.trellis` exclusion and
  still discover product code, tests, and repository scripts.
- Bad: `AGENTS.md` names `.trellis/workflow.md`, but that file exists only as an
  ignored local file.
- Bad: a developer's `.git/info/exclude` hides `.trellis/scripts`, making local Ruff
  pass while a clean CI checkout fails, or Ruff exclusions also hide `src` or `tests`.

### 6. Tests Required

For the exact staged snapshot:

```bash
git diff --cached --check
make setup PYTHON=/path/to/python3.11+
make check
make test-all
.venv/bin/python -m ruff format --check --no-respect-gitignore .
.venv/bin/python -m ruff check --no-respect-gitignore .
```

Assert that:

- every explicit required repository-owned path in committed instruction files
  exists, excluding identified optional/generated examples, placeholders, and globs;
- forbidden Host paths, local task archives, and secret-like values are absent;
- no unrelated paths are staged;
- the full suite passes from a clean temporary worktree.
- parsed TOML requires the exact Ruff exclusion `extend-exclude = [".trellis"]`,
  including equivalent multiline/commented TOML, and rejects product-path exclusions.

### 7. Wrong vs Correct

#### Wrong

```text
Commit AGENTS.md
Keep .trellis/workflow.md and .trellis/scripts/ ignored locally
Assume another developer can regenerate the missing contract
Rely on .git/info/exclude to hide generated Trellis files from Ruff
```

#### Correct

```text
Commit the repository-owned instructions and their complete referenced core together
Keep only optional Host adapters local
Validate the exact staged tree from a clean checkout
Declare the exact .trellis Ruff exclusion in pyproject.toml
```
