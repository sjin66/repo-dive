import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
SKILL_ROOT = ROOT / "skills/wiki"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
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
