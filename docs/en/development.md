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
tests/performance/    deterministic scale and resource-budget tests
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

## Scale and Performance Budgets

Run the deterministic scale checks separately when changing Scanner, Parser,
indexing, retrieval, Context packing, or Wiki Evidence behavior:

```bash
.venv/bin/pytest tests/performance -q
```

These tests generate repositories at runtime. They do not assert absolute
milliseconds, which vary by machine. They compare work and memory trends: a
four-times-larger corpus must stay within a six-times peak-memory envelope,
changing one file in a 64-file repository must rebuild exactly one file, and
Search, Context, and Wiki collections must remain within public result and
token budgets.

The recommended interactive operating envelope is up to 5,000 selected source
files or 50,000 Chunks. This is guidance, not a hard repository cap. For a
larger monorepo, narrow the corpus with `--include` and `--exclude`, then run
the performance suite or a representative local measurement before relying on
interactive latency. Exact BM25 and optional Vector retrieval currently read
the persisted Chunk corpus once per query, so their working memory grows
linearly with selected corpus size. Returned Search/Context/Wiki collections
remain bounded independently of corpus size.

Scanner reads source through fixed 64 KiB blocks, hashes the complete file,
and stops retaining source bytes after the configured file limit is crossed.
Parser receives and processes one `SourceFile` at a time in deterministic
order. Index publication uses a new generation, and incremental rebuild work
is proportional to changed files and Chunks rather than the full parse count.

| Boundary | Default or recommendation | Hard behavior |
| --- | --- | --- |
| Selected repository | Recommend at most 5,000 files or 50,000 Chunks | No global hard cap; narrow larger corpora explicitly |
| Source file | `--max-file-size 1000000` bytes | Larger files are recorded as `skipped` with `too_large`; this is not a command failure |
| Chunk | `--max-chunk-lines 200` | The value must be positive; invalid CLI input returns `invalid_invocation` and exit code 2 |
| Query | At most 1,000 characters | Empty or oversized input returns `invalid_invocation` and exit code 2 |
| Search candidates | Internal maximum 200 | Never exposed as an unbounded result collection |
| Search results | Default 10, hard maximum 50 | Values outside 1–50 return `invalid_invocation` and exit code 2 |
| Context/Wiki Evidence budget | Required; 1,200–8,000 tokens recommended | Must be positive; whole Chunks only, `estimated_tokens <= token_budget`, at most 50 retrieved results |
| Wiki structure input | 1,000,000 bytes | `wiki_structure_input_too_large`, exit code 2 |
| Wiki page input/body | 1,500,000 / 200,000 bytes | `wiki_page_input_too_large` / `wiki_page_body_too_large`, exit code 2 |

Do not loosen a threshold merely because a test is slow on one machine. First
compare work counts, corpus ratios, and peak-memory ratios, then profile the
specific path. Keep an optimization only when the same measurement shows a
change larger than run-to-run variance and the correctness suite remains green.

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
