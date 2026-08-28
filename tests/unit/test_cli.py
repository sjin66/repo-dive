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
    assert "local repository evidence" in capsys.readouterr().out
