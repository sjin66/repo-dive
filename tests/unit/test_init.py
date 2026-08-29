from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from repo_dive.commands import init as init_command
from repo_dive.errors import InvocationError
from repo_dive.initialization import install_skill


def _skill_source(tmp_path: Path, content: str = "skill\n") -> Path:
    source = tmp_path / "source"
    (source / "references").mkdir(parents=True)
    (source / "SKILL.md").write_text(content, encoding="utf-8")
    (source / "references/workflow.md").write_text("reference\n", encoding="utf-8")
    return source


def test_install_deduplicates_shared_agent_destination(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()

    result = install_skill(
        repository,
        agents=("codex", "opencode", "gemini-cli", "github-copilot"),
        source=_skill_source(tmp_path),
    )

    assert result.agents == ("codex", "opencode", "gemini-cli", "github-copilot")
    assert len(result.destinations) == 1
    destination = result.destinations[0]
    assert destination.path == ".agents/skills/wiki"
    assert destination.agents == result.agents
    assert destination.status == "installed"
    assert (repository / destination.path / "SKILL.md").read_text() == "skill\n"


def test_install_is_idempotent_and_force_replaces_conflicts(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    source = _skill_source(tmp_path)

    first = install_skill(repository, agents=("claude-code",), source=source)
    second = install_skill(repository, agents=("claude-code",), source=source)
    destination = repository / ".claude/skills/wiki"
    destination.joinpath("SKILL.md").write_text("different\n", encoding="utf-8")

    with pytest.raises(InvocationError, match="already contains different content"):
        install_skill(repository, agents=("claude-code",), source=source)
    assert destination.joinpath("SKILL.md").read_bytes() == b"different\n"

    forced = install_skill(
        repository, agents=("claude-code",), source=source, force=True
    )

    assert first.destinations[0].status == "installed"
    assert second.destinations[0].status == "reused"
    assert forced.destinations[0].status == "replaced"
    assert destination.joinpath("SKILL.md").read_bytes() == b"skill\n"


def test_install_validates_every_conflict_before_writing(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    conflict = repository / ".agents/skills/wiki"
    conflict.mkdir(parents=True)
    conflict.joinpath("SKILL.md").write_text("keep me\n", encoding="utf-8")

    with pytest.raises(InvocationError):
        install_skill(
            repository,
            agents=("claude-code", "codex"),
            source=_skill_source(tmp_path),
        )

    assert not (repository / ".claude/skills/wiki").exists()
    assert conflict.joinpath("SKILL.md").read_bytes() == b"keep me\n"


def test_install_rejects_symlinked_destination_parent(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (repository / ".claude").symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(InvocationError, match="symbolic link"):
        install_skill(
            repository,
            agents=("claude-code",),
            source=_skill_source(tmp_path),
            force=True,
        )

    assert tuple(elsewhere.iterdir()) == ()


def test_install_rolls_back_all_destinations_when_commit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    source = _skill_source(tmp_path)
    real_replace = os.replace
    published_destinations = 0

    def fail_second_publish(
        source_path: str | Path, destination_path: str | Path
    ) -> None:
        nonlocal published_destinations
        destination = Path(destination_path)
        if destination.name == "wiki":
            published_destinations += 1
            if published_destinations == 2:
                raise OSError("simulated publish failure")
        real_replace(source_path, destination_path)

    monkeypatch.setattr("repo_dive.initialization.os.replace", fail_second_publish)

    with pytest.raises(OSError, match="simulated publish failure"):
        install_skill(
            repository,
            agents=("claude-code", "codex"),
            source=source,
        )

    assert not (repository / ".claude/skills/wiki").exists()
    assert not (repository / ".agents/skills/wiki").exists()
    assert not tuple(repository.glob(".repo-dive-init-*"))


def test_forced_install_restores_replaced_content_when_commit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    source = _skill_source(tmp_path)
    old_files = {
        ".claude/skills/wiki/SKILL.md": b"old claude\n",
        ".agents/skills/wiki/SKILL.md": b"old shared\n",
    }
    for relative_path, content in old_files.items():
        path = repository / relative_path
        path.parent.mkdir(parents=True)
        path.write_bytes(content)

    real_replace = os.replace
    published_destinations = 0

    def fail_second_publish(
        source_path: str | Path, destination_path: str | Path
    ) -> None:
        nonlocal published_destinations
        destination = Path(destination_path)
        if destination.name == "wiki":
            published_destinations += 1
            if published_destinations == 2:
                raise OSError("simulated publish failure")
        real_replace(source_path, destination_path)

    monkeypatch.setattr("repo_dive.initialization.os.replace", fail_second_publish)

    with pytest.raises(OSError, match="simulated publish failure"):
        install_skill(
            repository,
            agents=("claude-code", "codex"),
            source=source,
            force=True,
        )

    for relative_path, content in old_files.items():
        assert (repository / relative_path).read_bytes() == content
    assert not tuple(repository.glob(".repo-dive-init-*"))


def test_noninteractive_command_requires_agent_without_reading_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": pytest.fail("non-TTY init must not read stdin"),
    )
    args = argparse.Namespace(
        repository=str(tmp_path), agent=[], force=False, format="markdown"
    )

    with pytest.raises(InvocationError, match="--agent is required"):
        init_command.handle(args)


def test_tty_command_prompts_for_multiple_agents_and_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _skill_source(tmp_path)
    answers = iter(("1,2,3,4,5", "y"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(init_command, "skill_resource_path", lambda: source)
    repository = tmp_path / "repo"
    repository.mkdir()
    args = argparse.Namespace(
        repository=str(repository), agent=[], force=False, format="markdown"
    )

    output = init_command.handle(args)

    assert output.format == "markdown"
    assert isinstance(output.result, str)
    assert "Claude Code" in output.result
    assert "GitHub Copilot" in output.result
    assert (repository / ".claude/skills/wiki/SKILL.md").is_file()
    assert (repository / ".agents/skills/wiki/SKILL.md").is_file()


def test_tty_command_cancellation_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter(("1", "n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    repository = tmp_path / "repo"
    repository.mkdir()
    args = argparse.Namespace(
        repository=str(repository), agent=[], force=False, format="markdown"
    )

    with pytest.raises(InvocationError, match="cancelled"):
        init_command.handle(args)

    assert not (repository / ".claude").exists()


@pytest.mark.parametrize("answer", ["", "0", "6", "one"])
def test_tty_command_rejects_invalid_or_empty_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    answer: str,
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": answer)
    args = argparse.Namespace(
        repository=str(tmp_path), agent=[], force=False, format="markdown"
    )

    with pytest.raises(InvocationError, match="selection|Select"):
        init_command.handle(args)


@pytest.mark.parametrize("stage", ["selection", "confirmation"])
def test_tty_command_treats_eof_as_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    answers: list[str | BaseException] = (
        [EOFError()] if stage == "selection" else ["1", EOFError()]
    )

    def answer(_prompt: str = "") -> str:
        value = answers.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", answer)
    args = argparse.Namespace(
        repository=str(tmp_path), agent=[], force=False, format="markdown"
    )

    with pytest.raises(InvocationError, match="cancelled"):
        init_command.handle(args)
