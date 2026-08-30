import io
import json
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SKILL_ROOT = ROOT / "skills/wiki"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX launcher tests require native POSIX process execution",
)
MANIFEST_PATHS = (
    ROOT / "plugin.json",
    ROOT / ".claude-plugin/plugin.json",
    ROOT / ".codex-plugin/plugin.json",
    ROOT / "gemini-extension.json",
)
HOST_SKILL_ROOTS = (
    ROOT / ".agents/skills",
    ROOT / ".claude/skills",
    ROOT / ".gemini/skills",
    ROOT / ".github/skills",
    ROOT / ".opencode/skills",
    ROOT / "skills",
)
PROJECT_MAPPINGS = {
    "Claude Code": ".claude/skills/wiki",
    "OpenAI Codex CLI": ".agents/skills/wiki",
    "OpenCode": ".agents/skills/wiki",
    "Gemini CLI": ".agents/skills/wiki",
    "GitHub Copilot": ".agents/skills/wiki",
}


def _write_fake_osascript(fake_bin: Path) -> None:
    parser = """\
import json
import sys

if len(sys.argv) != 6 or sys.argv[1:4] != ["-l", "JavaScript", "-"]:
    raise SystemExit(2)
with open(sys.argv[4], encoding="utf-8") as source:
    release = json.load(source)
target = release.get("targets", {}).get(sys.argv[5])
if release.get("schema_version") != "1.0" or not isinstance(target, dict):
    raise SystemExit(1)
fields = (
    release.get("version", ""),
    release.get("repository", ""),
    release.get("tag", ""),
    target.get("archive", ""),
    target.get("archive_type", ""),
    target.get("top_level", ""),
    target.get("executable", ""),
)
sys.stdout.write("\\t".join(str(field) for field in fields))
"""
    (fake_bin / "osascript").write_text(
        "#!/bin/sh\n"
        f'exec {shlex.quote(sys.executable)} -c {shlex.quote(parser)} "$@"\n',
        encoding="utf-8",
    )


def _frontmatter(content: str) -> dict[str, str]:
    opening, frontmatter, _body = content.split("---", maxsplit=2)
    assert opening == ""
    return dict(
        (key.strip(), value.strip())
        for line in frontmatter.strip().splitlines()
        for key, value in (line.split(":", maxsplit=1),)
    )


def _local_markdown_links(path: Path) -> tuple[Path, ...]:
    content = path.read_text(encoding="utf-8")
    links = re.findall(r"\[[^]]+\]\(([^)]+)\)", content)
    return tuple(
        (path.parent / link).resolve()
        for link in links
        if not link.startswith(("#", "http://", "https://"))
    )


def test_portable_wiki_skill_is_self_contained_and_unique() -> None:
    content = SKILL_PATH.read_text(encoding="utf-8")
    metadata = _frontmatter(content)

    assert metadata == {
        "name": "wiki",
        "description": (
            "Generate or refresh an evidence-grounded repository Wiki with the "
            "repo-dive CLI. Use when asked to document a codebase, explain its "
            "architecture, create onboarding documentation, or build a repository Wiki."
        ),
    }
    assert (SKILL_ROOT / "references/workflow-contract.md").is_file()
    portable_skills = tuple((ROOT / "skills").glob("*/SKILL.md"))
    assert portable_skills == (SKILL_PATH,)

    wiki_skill_paths = []
    for root in HOST_SKILL_ROOTS:
        if not root.is_dir():
            continue
        for path in root.glob("*/SKILL.md"):
            if _frontmatter(path.read_text(encoding="utf-8")).get("name") == "wiki":
                wiki_skill_paths.append(path)
    assert wiki_skill_paths == [SKILL_PATH]

    links = _local_markdown_links(SKILL_PATH)
    assert links
    for markdown_path in SKILL_ROOT.rglob("*.md"):
        for target in _local_markdown_links(markdown_path):
            assert target.is_relative_to(SKILL_ROOT.resolve())
            assert target.is_file()


def test_skill_preserves_the_cli_workflow_and_model_boundary() -> None:
    content = SKILL_PATH.read_text(encoding="utf-8")
    required_literals = (
        "command -v repo-dive",
        "do not silently download or install software",
        "do not clone it",
        "git status --short",
        "repo-dive index",
        "repo-dive wiki structure",
        "repo-dive wiki evidence",
        "repo-dive wiki page",
        "repo-dive wiki status",
        "repo-dive wiki build",
        "--format json",
        "exit code",
        "current Agent model",
        "CLI calls a generative model",
        "<repository>/.repo-dive/wiki.md",
    )

    for literal in required_literals:
        assert literal in content


def test_platform_manifests_share_package_identity_and_version() -> None:
    manifests = [
        json.loads(path.read_text(encoding="utf-8")) for path in MANIFEST_PATHS
    ]

    assert {manifest["name"] for manifest in manifests} == {"repo-dive"}
    assert {manifest["version"] for manifest in manifests} == {"0.1.0"}
    assert manifests[0]["$schema"] == (
        "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    )
    assert manifests[2]["skills"] == "./skills/"
    assert not (ROOT / ".opencode/plugins/repo-dive.ts").exists()


def test_marketplace_release_metadata_is_versioned_and_target_complete() -> None:
    release = json.loads(
        (SKILL_ROOT / "references/release.json").read_text(encoding="utf-8")
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert release["schema_version"] == "1.0"
    assert release["version"] == project["project"]["version"] == "0.1.0"
    assert release["repository"] == "https://github.com/sjin66/repo-dive"
    assert release["tag"] == f"v{release['version']}"
    assert set(release["targets"]) == {
        "darwin-arm64",
        "darwin-x64",
        "windows-x64",
    }
    assert {value["top_level"] for value in release["targets"].values()} == {
        "repo-dive"
    }
    assert release["targets"]["windows-x64"]["executable"] == "repo-dive.exe"
    assert release["targets"]["darwin-arm64"]["archive_type"] == "tar.gz"
    assert release["targets"]["windows-x64"]["archive_type"] == "zip"


def test_bootstrap_launchers_are_portable_skill_resources() -> None:
    posix = SKILL_ROOT / "scripts/repo-dive"
    powershell = SKILL_ROOT / "scripts/repo-dive.ps1"

    assert posix.is_file()
    assert powershell.is_file()
    if sys.platform != "win32":
        assert posix.stat().st_mode & 0o111
    assert "--install" in posix.read_text(encoding="utf-8")
    assert "--install" in powershell.read_text(encoding="utf-8")


@POSIX_ONLY
def test_posix_launcher_rejects_unsupported_platform_before_network(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text("#!/bin/sh\necho Linux\n", encoding="utf-8")
    (fake_bin / "curl").write_text(
        "#!/bin/sh\necho network-was-used >&2\nexit 99\n", encoding="utf-8"
    )
    for path in fake_bin.iterdir():
        path.chmod(0o755)

    completed = subprocess.run(
        [SKILL_ROOT / "scripts/repo-dive", "--install"],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": f"{fake_bin}:/usr/bin:/bin", "HOME": str(tmp_path)},
    )

    assert completed.returncode != 0
    assert "unsupported platform" in completed.stderr.lower()
    assert "network-was-used" not in completed.stderr


@POSIX_ONLY
def test_posix_launcher_rejects_unsafe_release_metadata_before_network(
    tmp_path: Path,
) -> None:
    skill = tmp_path / "wiki"
    shutil.copytree(SKILL_ROOT, skill)
    metadata_path = skill / "references/release.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["version"] = "../../escape"
    metadata["tag"] = "v../../escape"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text(
        '#!/bin/sh\nif [ "${1-}" = -s ]; then echo Darwin; else echo arm64; fi\n',
        encoding="utf-8",
    )
    _write_fake_osascript(fake_bin)
    (fake_bin / "curl").write_text(
        "#!/bin/sh\necho network-was-used >&2\nexit 99\n", encoding="utf-8"
    )
    for path in fake_bin.iterdir():
        path.chmod(0o755)

    completed = subprocess.run(
        [skill / "scripts/repo-dive", "--install"],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": f"{fake_bin}:/usr/bin:/bin", "HOME": str(tmp_path)},
    )

    assert completed.returncode != 0
    assert "unsafe version" in completed.stderr
    assert "network-was-used" not in completed.stderr


@POSIX_ONLY
def test_posix_launcher_installs_verified_archive_and_forwards_exit_status(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "payload/repo-dive"
    payload.mkdir(parents=True)
    executable = payload / "repo-dive"
    executable.write_text(
        "#!/bin/sh\n"
        "if [ \"${1-}\" = --version ]; then echo 'repo-dive 0.1.0'; exit 0; fi\n"
        "printf 'forwarded:%s\\n' \"$*\"\nexit 7\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    archive = tmp_path / "repo-dive-v0.1.0-darwin-arm64.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(payload, arcname="repo-dive")
    digest = subprocess.run(
        ["shasum", "-a", "256", archive],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()[0]
    checksums = tmp_path / "SHA256SUMS"
    checksums.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text(
        '#!/bin/sh\nif [ "${1-}" = -s ]; then echo Darwin; else echo arm64; fi\n',
        encoding="utf-8",
    )
    _write_fake_osascript(fake_bin)
    (fake_bin / "curl").write_text(
        "#!/bin/sh\nout=\nurl=\n"
        'while [ $# -gt 0 ]; do case "$1" in -o|--output) out=$2; shift 2;; '
        "http*) url=$1; shift;; *) shift;; esac; done\n"
        'cp "$FIXTURES/${url##*/}" "$out"\n',
        encoding="utf-8",
    )
    for path in fake_bin.iterdir():
        path.chmod(0o755)
    environment = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "FIXTURES": str(tmp_path),
    }
    launcher = SKILL_ROOT / "scripts/repo-dive"

    installed = subprocess.run(
        [launcher, "--install"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    forwarded = subprocess.run(
        [launcher, "alpha", "two words"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert installed.returncode == 0, installed.stderr
    assert "installed repo-dive 0.1.0" in installed.stderr
    assert forwarded.returncode == 7
    assert forwarded.stdout == "forwarded:alpha two words\n"


@POSIX_ONLY
def test_posix_launcher_rejects_archive_traversal_without_publishing(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "repo-dive-v0.1.0-darwin-arm64.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        body = b"escape"
        info = tarfile.TarInfo("repo-dive/../../escape")
        info.size = len(body)
        bundle.addfile(info, io.BytesIO(body))
    digest = subprocess.run(
        ["shasum", "-a", "256", archive],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()[0]
    (tmp_path / "SHA256SUMS").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text(
        '#!/bin/sh\nif [ "${1-}" = -s ]; then echo Darwin; else echo arm64; fi\n',
        encoding="utf-8",
    )
    _write_fake_osascript(fake_bin)
    (fake_bin / "curl").write_text(
        "#!/bin/sh\nout=\nurl=\n"
        'while [ $# -gt 0 ]; do case "$1" in -o|--output) out=$2; shift 2;; '
        "http*) url=$1; shift;; *) shift;; esac; done\n"
        'cp "$FIXTURES/${url##*/}" "$out"\n',
        encoding="utf-8",
    )
    for path in fake_bin.iterdir():
        path.chmod(0o755)
    home = tmp_path / "home"
    completed = subprocess.run(
        [SKILL_ROOT / "scripts/repo-dive", "--install"],
        check=False,
        capture_output=True,
        text=True,
        env={
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "HOME": str(home),
            "FIXTURES": str(tmp_path),
        },
    )

    assert completed.returncode != 0
    assert "unsafe path" in completed.stderr
    assert not (home / ".cache/repo-dive/0.1.0/darwin-arm64").exists()
    assert not (tmp_path / "escape").exists()


def test_bilingual_install_guides_document_project_platform_mappings() -> None:
    guides = (
        ROOT / "docs/en/agent-plugin.md",
        ROOT / "docs/zh-CN/agent-plugin.md",
    )
    required_literals = (
        "claude-code",
        "codex",
        "opencode",
        "gemini-cli",
        "github-copilot",
        ".claude/skills/wiki",
        ".agents/skills/wiki",
        "repo-dive",
        "repo-dive init",
        "--agent",
        "--force",
        "--format json",
        "reused",
        "skills remove wiki",
        ".repo-dive/wiki.md",
    )

    for guide in guides:
        content = guide.read_text(encoding="utf-8")
        for literal in required_literals:
            assert literal in content
        for host, destination in PROJECT_MAPPINGS.items():
            assert re.search(
                rf"\| {re.escape(host)} \| `{re.escape(destination)}` \|", content
            )

        assert "gh skill list" in content
        assert "gemini skills uninstall wiki --scope workspace" in content
        assert "gemini extensions uninstall repo-dive" in content
        assert "copilot plugin uninstall repo-dive" in content
