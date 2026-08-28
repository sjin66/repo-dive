# repo-dive

[简体中文](README.zh-CN.md)

`repo-dive` is a pure-Python CLI that helps coding agents collect grounded evidence from a local repository and assemble repository-owned knowledge artifacts.

The CLI is intentionally not another agent. It performs deterministic repository work; GitHub Copilot or another calling agent interprets the evidence and writes the prose.

## Status

The current foundation provides:

- an installable `repo-dive` command with `--help` and `--version`;
- authoritative cross-agent instructions;
- bilingual architecture, CLI, workflow, and development contracts;
- shared local/CI verification entry points;
- test and evaluation scaffolding.

Repository scanning, syntax parsing, indexing, retrieval, context assembly, and wiki generation are planned but not implemented yet.

## Design Philosophy

- deterministic core, probabilistic edge;
- evidence before narrative;
- inspectable and resumable stages;
- stable JSON, exit-code, and filesystem contracts;
- local-first ownership of source and generated artifacts;
- replaceable parsing and retrieval components;
- one harness for humans, agents, and CI.

See [Architecture](docs/en/architecture.md) for the complete rationale.

## Intended Agent Workflow

The planned workflow is:

```text
calling agent
  -> invoke repo-dive to scan/index a local repository
  -> request structured evidence for one wiki page
  -> generate prose using the caller's current model
  -> return the page to repo-dive for persistence
  -> ask repo-dive to assemble the final Markdown
```

The stable final artifact is:

```text
<repository>/.repo-dive/wiki.md
```

See [Wiki Workflow](docs/en/wiki-workflow.md) for stage and artifact details.

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
```

See [Development](docs/en/development.md) and [CLI Contract](docs/en/cli-contract.md) before implementing commands.

## Project Documentation

- [Architecture](docs/en/architecture.md)
- [CLI Contract](docs/en/cli-contract.md)
- [Wiki Workflow](docs/en/wiki-workflow.md)
- [Development](docs/en/development.md)
- [Agent Guide](AGENTS.md)

