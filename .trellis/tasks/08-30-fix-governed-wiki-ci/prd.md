# Fix governed Wiki CI failure

## Goal

Restore GitHub Actions on `feature/cli-agent-marketplace` by making Ruff's checked
source boundary deterministic between developer clones and clean CI checkouts.

## Background

- GitHub Actions run `33305587188` fails for Python 3.11, 3.12, and 3.13 in
  `make check` before tests run.
- Ruff `0.16.5` reports 20 generated files under `.trellis/scripts/` would be
  reformatted in a clean checkout.
- The local clone's `.git/info/exclude` contains `/.trellis/scripts/`, so ordinary
  `ruff format --check .` discovery skips those tracked files locally and previously
  produced a false pass.
- `.trellis/scripts/` is generated Trellis runtime tooling. Project type checking
  already scopes itself to `src`, `tests`, and `scripts`; the product quality gate does
  not own formatting of generated `.trellis` runtime files.

## Requirements

- Add a repository-owned Ruff exclusion for `.trellis` so format and lint discovery do
  not depend on clone-local Git excludes.
- Keep Ruff checks active for product code and repository-owned `scripts/`.
- Do not bulk-format or otherwise modify generated `.trellis/scripts/` files.
- Do not weaken tests, package checks, type checking, repository contracts, or release
  contracts.
- Reproduce the clean-checkout condition locally with Ruff's
  `--no-respect-gitignore` option before accepting the fix.

## Acceptance Criteria

- [ ] `.venv/bin/python -m ruff format --check --no-respect-gitignore .` passes without
  inspecting generated `.trellis` runtime files.
- [ ] `.venv/bin/python -m ruff check --no-respect-gitignore .` passes.
- [ ] `make check` passes.
- [ ] `make test-all` and `make package-smoke` retain their existing outcomes.
- [ ] A pushed commit triggers a successful GitHub Actions CI run across the configured
  Python matrix.

## Out Of Scope

- Reformatting or changing Trellis runtime behavior.
- Changing GitHub Actions matrix versions or skipping `make check`.
- Fixing the known local duplicate Wiki Skill installation test, which is not present in
  clean CI.
