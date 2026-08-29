"""Public `repo-dive init` command boundary."""

from __future__ import annotations

import argparse
import sys
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from repo_dive.commands import Command, CommandOutput, OutputFormat
from repo_dive.errors import InvocationError
from repo_dive.initialization import SUPPORTED_AGENTS, InitResult, install_skill
from repo_dive.schema import JsonObject
from repo_dive.storage.paths import resolve_repository

AGENT_LABELS = {
    "claude-code": "Claude Code",
    "codex": "OpenAI Codex CLI",
    "opencode": "OpenCode",
    "gemini-cli": "Gemini CLI",
    "github-copilot": "GitHub Copilot",
}


def configure(parser: argparse.ArgumentParser) -> None:
    """Configure project-scoped Agent Skill initialization."""
    parser.add_argument(
        "repository",
        nargs="?",
        default=".",
        help="local repository directory (default: current directory)",
    )
    parser.add_argument(
        "--agent",
        action="append",
        choices=SUPPORTED_AGENTS,
        default=[],
        help="Agent to initialize; repeatable",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace existing different wiki skill content",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="result output format (default: markdown)",
    )


def skill_resource_path() -> Traversable:
    """Return the packaged skill, with an editable-checkout fallback."""
    packaged = files("repo_dive").joinpath("_skills/wiki")
    if packaged.is_dir():
        return packaged
    return Path(__file__).parents[3] / "skills/wiki"


def handle(args: argparse.Namespace) -> CommandOutput:
    """Select Agents when needed and install the bundled skill offline."""
    agents = tuple(args.agent)
    if not agents:
        if args.format == "json" or not sys.stdin.isatty():
            raise InvocationError(
                "agent_required",
                "--agent is required in JSON mode or non-TTY execution.",
            )
        agents = _prompt_for_agents()
        if not _confirm(agents, force=args.force):
            raise InvocationError("init_cancelled", "Initialization cancelled.")

    root = resolve_repository(args.repository)
    result = install_skill(
        root,
        agents=agents,
        source=skill_resource_path(),
        force=args.force,
    )
    output_format: OutputFormat = args.format
    output = (
        _markdown_result(result)
        if output_format == "markdown"
        else _json_result(result)
    )
    return CommandOutput(
        command="init",
        format=output_format,
        result=output,
        repository=str(root),
    )


def _prompt_for_agents() -> tuple[str, ...]:
    print("Select one or more Agents (comma-separated numbers):")
    for index, agent in enumerate(SUPPORTED_AGENTS, start=1):
        print(f"  {index}. {AGENT_LABELS[agent]}")
    raw_selection = _interactive_input("Agents: ").strip()
    if not raw_selection:
        raise InvocationError(
            "invalid_agent_selection", "Agent selection must not be empty."
        )
    try:
        indexes = tuple(int(value.strip()) for value in raw_selection.split(","))
    except ValueError as error:
        raise InvocationError(
            "invalid_agent_selection",
            "Agent selection must use comma-separated numbers.",
        ) from error
    if not indexes or any(
        index < 1 or index > len(SUPPORTED_AGENTS) for index in indexes
    ):
        raise InvocationError(
            "invalid_agent_selection", "Select at least one listed Agent."
        )
    return tuple(SUPPORTED_AGENTS[index - 1] for index in dict.fromkeys(indexes))


def _confirm(agents: tuple[str, ...], *, force: bool) -> bool:
    labels = ", ".join(AGENT_LABELS[agent] for agent in agents)
    action = "Install (replacing conflicts)" if force else "Install"
    answer = _interactive_input(f"{action} wiki for {labels}? [y/N] ")
    return answer.strip().lower() in {
        "y",
        "yes",
    }


def _interactive_input(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt) as error:
        raise InvocationError("init_cancelled", "Initialization cancelled.") from error


def _json_result(result: InitResult) -> JsonObject:
    return {
        "agents": list(result.agents),
        "destinations": [
            {
                "agents": list(destination.agents),
                "path": destination.path,
                "status": destination.status,
            }
            for destination in result.destinations
        ],
    }


def _markdown_result(result: InitResult) -> str:
    lines = ["# Agent Skill initialization", "", "Selected Agents:"]
    lines.extend(f"- {AGENT_LABELS[agent]}" for agent in result.agents)
    lines.extend(("", "Destinations:"))
    lines.extend(
        f"- `{destination.path}`: {destination.status} "
        f"({', '.join(AGENT_LABELS[agent] for agent in destination.agents)})"
        for destination in result.destinations
    )
    return "\n".join(lines) + "\n"


INIT_COMMAND = Command(
    name="init",
    help="install the bundled wiki skill into project Agent discovery paths",
    configure=configure,
    handler=handle,
)

__all__ = ["INIT_COMMAND"]
