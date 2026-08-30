from __future__ import annotations

from pathlib import Path

import pytest

from repo_dive.errors import InvocationError
from repo_dive.parsing.models import create_chunk
from repo_dive.wiki.assembler import WikiBuildContext, assemble_wiki, subsection_anchor
from repo_dive.wiki.models import (
    EvidenceRef,
    Metadata,
    Page,
    PageStatus,
    Section,
    Subsection,
    SubsectionContent,
    Wiki,
    metadata_from_document,
    wiki_from_document,
)
from repo_dive.wiki.service import _extension_boundary_paths, structure_from_document
from repo_dive.wiki.submission import (
    PageSubmission,
    page_submission_from_document,
    validate_submission_content,
)


def _subsection() -> Subsection:
    return Subsection(
        id="first_run",
        title="First run",
        description="Explain the first successful command.",
        direct_source_paths=("src/app.py",),
    )


def _evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="evidence:one",
        chunk_id="chunk:one",
        path="src/app.py",
        start_line=1,
        end_line=8,
        content_hash="hash",
        role="direct",
        subsection_ids=("first_run",),
        direct_paths=("src/app.py",),
    )


def _page(body: str = "Run the command.\n") -> Page:
    return Page(
        id="installation",
        title="Installation",
        description="Install and run the tool.",
        status=PageStatus.GENERATED,
        evidence=(_evidence(),),
        citation_ids=("evidence:one",),
        subsections=(_subsection(),),
        subsection_contents=(SubsectionContent("first_run", body, ("evidence:one",)),),
    )


def _wiki(body: str = "Run the command.\n") -> Wiki:
    return Wiki(
        title="Example Wiki",
        description="Grounded documentation.",
        sections=(Section("guide", "Guide", (_page(body),)),),
        framework_labels=(
            ("contents", "目录"),
            ("default_exclusions", "默认排除目录"),
            ("exclude_patterns", "排除模式"),
            ("generated_at", "生成时间"),
            ("git_scope", "Git 语料库"),
            ("git_scope_description", "应用过滤器后的 Git 文件"),
            ("include_patterns", "包含模式"),
            ("index_build", "索引构建"),
            ("indexed_files", "已索引文件"),
            ("patterns_none", "无"),
            ("related_pages", "相关页面"),
            ("repository_fingerprint", "代码库指纹"),
            ("scan_mode", "扫描模式"),
            ("scope_version", "范围与版本"),
            ("skipped_files", "已跳过文件"),
            ("source_commit", "源提交"),
            ("source_commit_none", "无"),
            ("source_state", "源状态"),
            ("source_state_clean", "干净"),
            ("source_state_dirty", "有未提交更改"),
            ("source_state_non_git", "非 Git"),
            ("sources", "来源"),
        ),
    )


def test_schema_two_round_trip_preserves_ordered_subsections_and_source_identity() -> (
    None
):
    wiki = _wiki()
    metadata = Metadata(
        repository=str(Path.cwd()),
        repository_fingerprint="fingerprint",
        source_commit="a" * 40,
        source_control="git",
        source_dirty=True,
        output_language="zh-CN",
        index_schema_version=4,
        index_build_id="build",
        created_at="2026-08-30T00:00:00Z",
        updated_at="2026-08-30T00:00:00Z",
    )

    assert wiki_from_document(wiki.to_document()) == wiki
    assert metadata_from_document(metadata.to_document()) == metadata
    assert wiki.to_document()["schema_version"] == "2.0"


def test_submission_rejects_cli_owned_heading_with_subsection_line() -> None:
    submission = PageSubmission(
        page_id="installation",
        subsections=(
            SubsectionContent(
                "first_run", "Text.\n\n#### Repeated heading\n", ("evidence:one",)
            ),
        ),
    )

    with pytest.raises(InvocationError) as captured:
        validate_submission_content(_page(), submission)

    assert captured.value.code == "wiki_page_heading_level_invalid"
    assert captured.value.details == {
        "line": 3,
        "page_id": "installation",
        "subsection_id": "first_run",
    }


def test_submission_rejects_raw_html_with_subsection_line() -> None:
    submission = PageSubmission(
        page_id="installation",
        subsections=(
            SubsectionContent(
                "first_run", "Text.\n\n<h1>Owned heading</h1>\n", ("evidence:one",)
            ),
        ),
    )

    with pytest.raises(InvocationError) as captured:
        validate_submission_content(_page(), submission)

    assert captured.value.code == "wiki_page_html_invalid"
    assert captured.value.details == {
        "line": 3,
        "page_id": "installation",
        "subsection_id": "first_run",
    }


def test_schema_two_requires_subsections_and_submission_shape_parity() -> None:
    structure = {
        "schema_version": "2.0",
        "title": "Wiki",
        "description": "Description",
        "output_language": "en",
        "sections": [
            {
                "id": "guide",
                "title": "Guide",
                "pages": [
                    {
                        "id": "page",
                        "title": "Page",
                        "description": "Description",
                        "relevant_files": [],
                        "related_page_ids": [],
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="Page structure fields are invalid"):
        structure_from_document(structure)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="fields are invalid"):
        page_submission_from_document(
            {
                "schema_version": "2.0",
                "page_id": "page",
                "body": "Body",
                "evidence_ids": ["evidence:one"],
            }
        )


def test_assembly_has_three_level_contents_hierarchy_and_localized_scope() -> None:
    context = WikiBuildContext(
        scan_mode="git",
        include=("src/**",),
        exclude=("tests/**",),
        effective_default_excluded_directories=(".git", ".repo-dive"),
        indexed_files=3,
        skipped_files=1,
        index_build_id="build",
        repository_fingerprint="fingerprint",
        source_control="git",
        source_commit="a" * 40,
        source_dirty=True,
        generated_at="2026-08-30T00:00:00Z",
    )

    markdown = assemble_wiki(_wiki("##### Details\n\nRun it.\n"), context)

    anchor = subsection_anchor("installation", "first_run")
    assert "**范围与版本**" in markdown
    assert f"    - [First run](#{anchor})" in markdown
    assert f'<a id="{anchor}"></a>\n#### First run' in markdown
    assert "##### Details" in markdown
    assert "#### 来源" in markdown


def test_extension_boundary_detection_requires_explicit_protocol_contracts() -> None:
    false_positive = create_chunk(
        path="src/messages.py",
        start_line=1,
        end_line=1,
        text="message = 'parser provider adapter retriever'\n",
    )
    parser_boundary = create_chunk(
        path="src/parsing/models.py",
        start_line=1,
        end_line=4,
        text=(
            "class ParserAdapter(Protocol):\n"
            "    def parse(self, file: FileRecord, text: str) -> ParseResult: ...\n"
        ),
    )
    provider_boundary = create_chunk(
        path="src/providers.py",
        start_line=1,
        end_line=4,
        text=(
            "class EmbeddingProvider(Protocol):\n"
            "    def embed(self, texts: Sequence[str]) -> tuple[float, ...]: ...\n"
        ),
    )
    commented_boundary = create_chunk(
        path="src/commented.py",
        start_line=1,
        end_line=2,
        text=(
            "# class ParserAdapter(Protocol):\n#     def parse(self, file, text): ...\n"
        ),
    )
    string_boundary = create_chunk(
        path="src/string.py",
        start_line=1,
        end_line=3,
        text=(
            "description = '''class ParserAdapter(Protocol):\n"
            "    def parse(self, file, text): ...\n'''\n"
        ),
    )

    assert (
        _extension_boundary_paths((false_positive, commented_boundary, string_boundary))
        == ()
    )
    assert _extension_boundary_paths(
        (false_positive, parser_boundary, provider_boundary)
    ) == ("src/parsing/models.py", "src/providers.py")
