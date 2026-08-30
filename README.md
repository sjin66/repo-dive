# repo-dive

[简体中文](README.zh-CN.md)

`repo-dive` is a pure-Python local-repository RAG CLI. It helps coding agents index source code, retrieve grounded evidence, and assemble repository-owned knowledge artifacts.

The CLI is intentionally not another agent. It performs deterministic repository work; GitHub Copilot or another calling agent interprets the evidence and writes the prose.

## Status

The current offline RAG core provides:

- deterministic Git/filesystem scanning with safe repository boundaries;
- Python AST and Tree-sitter parsing with stable chunks, symbols, and relationships;
- atomic local SQLite indexing with BM25 and structural retrieval;
- read-only `search` and token-budgeted `context` commands in JSON or Markdown;
- resumable `wiki structure`, `wiki evidence`, `wiki page`, `wiki build`, and `wiki status` commands with atomic artifacts;
- stable process, schema, evaluation, and local/CI harness contracts.

The optional SQLite float32 Vector Store, deterministic cosine retriever,
explicit local Sentence Transformers provider, and three-channel
`index`/`search`/`context` integration are implemented. The offline Wiki
workflow remains complete and unchanged.

## Design Philosophy

- deterministic core, probabilistic edge;
- evidence before narrative;
- hybrid RAG across syntax structure, BM25 lexical search, and optional vectors;
- inspectable and resumable stages;
- stable JSON, exit-code, and filesystem contracts;
- local-first ownership of source and generated artifacts;
- replaceable parsing and retrieval components;
- one harness for humans, agents, and CI.

See [Architecture](docs/en/architecture.md) for the complete rationale.

## Agent Workflow

The available end-to-end Wiki RAG flow is:

```text
calling agent
  -> invoke repo-dive to scan and parse a local repository
  -> build structural, BM25, and optional vector indexes
  -> retrieve and budget structured evidence for one wiki page
  -> generate prose using the caller's current model
  -> return the page to repo-dive for persistence
  -> ask repo-dive to assemble the final Markdown
```

The stable final artifact is:

```text
<repository>/.repo-dive/wiki.md
```

See [Wiki Workflow](docs/en/wiki-workflow.md) for stage and artifact details.
To install the portable `wiki` skill for supported coding agents, see
[Agent Plugin Installation](docs/en/agent-plugin.md).

```bash
repo-dive init . --agent claude-code --agent codex --agent opencode \
  --agent gemini-cli --agent github-copilot
npx skills add sjin66/repo-dive --skill wiki -a opencode -y
```

In a terminal, bare `repo-dive init` offers an interactive multi-select. The
command installs project-scoped skill files offline. The `npx skills` route
supports OpenCode without Python: after explicit first-use consent, the Skill
installs a checksummed self-contained runtime on supported targets.

In this design, RAG means **retrieval-augmented generation with a split execution boundary**: `repo-dive` owns ingestion, indexing, retrieval, ranking, and context packaging; the calling Copilot session owns generation. The CLI does not launch a second hidden model session.

## GitHub Copilot Quick Start

No MCP server is required. After `make setup`, GitHub Copilot or another agent
can call the executable directly. For a grounded repository answer:

```bash
.venv/bin/repo-dive index /path/to/repository --format json
.venv/bin/repo-dive context /path/to/repository "How does startup work?" --token-budget 1200 --max-results 10 --format json
```

The caller generates its answer from `result.items` and cites each item's
`path`, `start_line`, and `end_line`. For a persistent Wiki, run the complete
resumable sequence:

```bash
.venv/bin/repo-dive index /path/to/repository --format json
.venv/bin/repo-dive wiki structure /path/to/repository --input structure.json --format json
.venv/bin/repo-dive wiki evidence /path/to/repository --page overview --token-budget 1200 --max-results 10 --format json
# The calling Copilot model writes page.json from the returned Evidence.
.venv/bin/repo-dive wiki page /path/to/repository --page overview --input page.json --format json
.venv/bin/repo-dive wiki status /path/to/repository --format json
.venv/bin/repo-dive wiki build /path/to/repository --format json
```

`wiki evidence` is the persisted Context stage for a Wiki page; do not replace
it with generic `context`. Page JSON may also be piped with `--input -`. Exit
codes are `0` success, `2` invalid invocation/input, `3` unavailable or stale
repository data, and `4` internal failure. On failure, keep the previous
`.repo-dive/` artifacts and recover according to the stable JSON error code.
See [CLI Contract](docs/en/cli-contract.md) for complete input/output and retry
examples.

## Development Setup

Python 3.11 or newer is required.

```bash
make setup
make check
make test-unit
make test-all
.venv/bin/python -m repo_dive.evaluation.runner evals/cases --format json
```

After setup:

```bash
.venv/bin/repo-dive --help
.venv/bin/repo-dive --version
.venv/bin/repo-dive init --agent github-copilot
.venv/bin/repo-dive index /path/to/repository --format json
.venv/bin/repo-dive search /path/to/repository "entrypoint" --max-results 10 --format json
.venv/bin/repo-dive context /path/to/repository "architecture" --token-budget 1200 --format json
.venv/bin/repo-dive index /path/to/repository --embedding-model /path/to/local/model --format json
.venv/bin/repo-dive search /path/to/repository "request lifecycle" --embedding-model /path/to/local/model --format json
.venv/bin/repo-dive wiki structure /path/to/repository --input structure.json --format json
.venv/bin/repo-dive wiki evidence /path/to/repository --page overview --token-budget 1200 --format json
.venv/bin/repo-dive wiki page /path/to/repository --page overview --input page.json --format json
.venv/bin/repo-dive wiki page /path/to/repository --page overview --input - --format json
.venv/bin/repo-dive wiki build /path/to/repository --format markdown
.venv/bin/repo-dive wiki status /path/to/repository --format json
```

See [Development](docs/en/development.md) and [CLI Contract](docs/en/cli-contract.md) for supported workflows and public contracts.

## Project Documentation

- [Architecture](docs/en/architecture.md)
- [CLI Contract](docs/en/cli-contract.md)
- [Wiki Workflow](docs/en/wiki-workflow.md)
- [Complete Wiki Generation Flow](docs/en/wiki-generation-flow.md)
- [Agent Plugin Installation](docs/en/agent-plugin.md)
- [Development](docs/en/development.md)
- [Agent Guide](AGENTS.md)
