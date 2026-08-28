# Development

## Requirements

- Python 3.11 or newer
- GNU Make
- Git

The project does not require Node.js, a web runtime, or a model-provider credential.

## Setup

Create the project-managed virtual environment and install the editable package with development tools:

```bash
make setup
```

The environment lives at `.venv/`. Override the bootstrap interpreter when necessary:

```bash
make setup PYTHON=/path/to/python3.12
```

### Optional local embeddings

The default development installation does not include or import Sentence
Transformers. Install the explicit vector extra only when developing the local
embedding adapter:

```bash
.venv/bin/python -m pip install -e ".[vector]"
```

The adapter accepts an existing local model directory. It passes
`local_files_only=True` and `trust_remote_code=False` to Sentence Transformers,
so a missing model is an error rather than a download request. Provider errors
and the persisted model identity do not expose the absolute model path. Use the
same model directory for explicit `index`, `search`, and `context` commands.
`--vector-failure strict` is the default; choose `degraded` only when an
observable BM25/structural fallback is acceptable.

## Shared Verification Commands

```bash
make check
make test-unit
make test-all
```

- `check` runs formatting checks, linting, type checking, and repository contract validation.
- `test-unit` runs focused tests under `tests/unit/`.
- `test-all` runs the complete test suite, including integration tests when present.

CI invokes the same targets. Do not add a tool command directly to CI without adding it to the relevant Make target first.

## Test-Driven Changes

For behavior changes:

1. Write one test describing the observable failure.
2. Run it and confirm it fails for the missing behavior.
3. Write the smallest implementation that passes.
4. Run the focused test and then the complete relevant suite.
5. Refactor only while tests remain green.

Tests should exercise real behavior. Human documentation does not need unit tests; repository-level documentation contracts belong in the `make check` validation script.

## Project Layout

```text
src/repo_dive/        Python package
tests/unit/           isolated behavior tests
tests/integration/    repository workflow tests
tests/fixtures/       small intentional repository fixtures
evals/cases/          machine-readable agent/RAG evaluation cases
docs/en/              English engineering documentation
docs/zh-CN/           Simplified Chinese counterparts
docs/superpowers/     approved specifications and implementation plans
```

## Documentation Changes

Update the English and Simplified Chinese files in the same commit. Keep technical constants, paths, exit codes, JSON field names, and command examples identical. Agent and harness policy belongs in root `AGENTS.md`; compatibility files reference it rather than copying it.

## Dependency Changes

Runtime dependencies must support Python 3.11 and have a clear boundary-owned purpose. Record the decision in the feature design, add it to `pyproject.toml`, and cover the adapter behavior without testing the dependency's own internals. Heavy or provider-specific dependencies belong in a named optional extra and must be imported lazily at their adapter boundary.

Development-only tools belong in the `dev` optional dependency. Keep `make setup` as the single installation path for contributors and CI.

## Evaluation Changes

Retrieval and context heuristics require a case under `evals/cases/`. Each case has a stable ID, category, prompt, and expected behavior. Cases that are not executable yet document the product contract without pretending the feature exists.

## Before Handoff

Run fresh commands from the repository root:

```bash
make check
make test-all
.venv/bin/repo-dive --help
.venv/bin/repo-dive --version
git status --short
```

Report actual command output and any remaining limitations. Do not claim planned commands are available.
