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
- resumable `wiki structure` and `wiki status` commands with atomic JSON state;
- stable process, schema, evaluation, and local/CI harness contracts.

Optional vector retrieval and wiki evidence/page/assembly commands remain planned work.

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

The available retrieval flow and planned wiki stages are:

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

In this design, RAG means **retrieval-augmented generation with a split execution boundary**: `repo-dive` owns ingestion, indexing, retrieval, ranking, and context packaging; the calling Copilot session owns generation. The CLI does not launch a second hidden model session.

## Development Setup

Python 3.11 or newer is required.

```bash
make setup
make check
make test-unit
make test-all
```

After setup:

```bash
.venv/bin/repo-dive --help
.venv/bin/repo-dive --version
.venv/bin/repo-dive index /path/to/repository --format json
.venv/bin/repo-dive search /path/to/repository "entrypoint" --max-results 10 --format json
.venv/bin/repo-dive context /path/to/repository "architecture" --token-budget 1200 --format json
.venv/bin/repo-dive wiki structure /path/to/repository --input structure.json --format json
.venv/bin/repo-dive wiki status /path/to/repository --format json
```

See [Development](docs/en/development.md) and [CLI Contract](docs/en/cli-contract.md) for supported workflows and public contracts.

## Project Documentation

- [Architecture](docs/en/architecture.md)
- [CLI Contract](docs/en/cli-contract.md)
- [Wiki Workflow](docs/en/wiki-workflow.md)
- [Development](docs/en/development.md)
- [Agent Guide](AGENTS.md)
