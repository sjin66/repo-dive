from __future__ import annotations

from dataclasses import replace

import pytest

from repo_dive.wiki.assembler import assemble_wiki, stable_anchor, subsection_anchor
from repo_dive.wiki.models import (
    EvidenceRef,
    Page,
    PageStatus,
    Section,
    Subsection,
    SubsectionContent,
    Wiki,
)


def evidence(
    evidence_id: str,
    path: str,
    start_line: int,
    end_line: int,
) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        chunk_id=f"chunk:{evidence_id}",
        path=path,
        start_line=start_line,
        end_line=end_line,
        content_hash=f"hash:{evidence_id}",
    )


def generated_page(
    page_id: str,
    title: str,
    body: str,
    reference: EvidenceRef,
    *,
    related_page_ids: tuple[str, ...] = (),
) -> Page:
    return Page(
        id=page_id,
        title=title,
        description=f"Explain {title}.",
        status=PageStatus.GENERATED,
        related_page_ids=related_page_ids,
        evidence=(reference,),
        citation_ids=(reference.evidence_id,),
        subsections=(
            Subsection(
                id="details",
                title="Details",
                description=f"Explain {title} details.",
                direct_source_paths=(reference.path,),
            ),
        ),
        subsection_contents=(
            SubsectionContent("details", body, (reference.evidence_id,)),
        ),
    )


def wiki() -> Wiki:
    overview = generated_page(
        "overview",
        "Overview",
        "The entrypoint delegates greeting construction.\n",
        evidence("evidence:overview", "src/app.py", 1, 4),
        related_page_ids=("utilities",),
    )
    utilities = generated_page(
        "utilities",
        "Utilities",
        "The helper formats a supplied name.\n\n",
        evidence(
            "evidence:utilities",
            "docs/My Guide [draft].md",
            2,
            4,
        ),
        related_page_ids=("overview",),
    )
    return Wiki(
        title="Example Wiki",
        description="Grounded repository documentation.",
        sections=(
            Section(
                id="guide",
                title="Guide",
                pages=(overview, utilities),
            ),
        ),
    )


def test_stable_anchor_has_a_safe_type_prefix_and_full_identifier_hash() -> None:
    assert stable_anchor("page", "overview") == (
        "page-bd445c462b7eebbc242e27f08c7d981e97fb28faf17ea73862bf95119b60e0f7"
    )
    assert stable_anchor("section", "overview") != stable_anchor("page", "overview")


def test_assemble_wiki_is_ordered_deterministic_and_links_grounded_sources() -> None:
    document = wiki()
    section_anchor = stable_anchor("section", "guide")
    overview_anchor = stable_anchor("page", "overview")
    utilities_anchor = stable_anchor("page", "utilities")
    overview_subsection = subsection_anchor("overview", "details")
    utilities_subsection = subsection_anchor("utilities", "details")

    markdown = assemble_wiki(document)

    assert markdown == (
        "# Example Wiki\n"
        "\n"
        "Grounded repository documentation.\n"
        "\n"
        "## Contents\n"
        "\n"
        f"- [Guide](#{section_anchor})\n"
        f"  - [Overview](#{overview_anchor})\n"
        f"    - [Details](#{overview_subsection})\n"
        f"  - [Utilities](#{utilities_anchor})\n"
        f"    - [Details](#{utilities_subsection})\n"
        "\n"
        f'<a id="{section_anchor}"></a>\n'
        "## Guide\n"
        "\n"
        f'<a id="{overview_anchor}"></a>\n'
        "### Overview\n"
        "\n"
        f'<a id="{overview_subsection}"></a>\n'
        "#### Details\n"
        "\n"
        "The entrypoint delegates greeting construction.\n"
        "\n"
        "#### Related pages\n"
        "\n"
        f"- [Utilities](#{utilities_anchor})\n"
        "\n"
        "#### Sources\n"
        "\n"
        "- [src/app.py:1-4](../src/app.py#L1-L4)\n"
        "\n"
        f'<a id="{utilities_anchor}"></a>\n'
        "### Utilities\n"
        "\n"
        f'<a id="{utilities_subsection}"></a>\n'
        "#### Details\n"
        "\n"
        "The helper formats a supplied name.\n"
        "\n"
        "#### Related pages\n"
        "\n"
        f"- [Overview](#{overview_anchor})\n"
        "\n"
        "#### Sources\n"
        "\n"
        "- [docs/My Guide \\[draft\\].md:2-4]"
        "(../docs/My%20Guide%20%5Bdraft%5D.md#L2-L4)\n"
    )
    assert assemble_wiki(document) == markdown


@pytest.mark.parametrize(
    "invalid_page",
    [
        replace(wiki().sections[0].pages[0], subsection_contents=()),
        replace(wiki().sections[0].pages[0], citation_ids=()),
    ],
)
def test_assemble_wiki_rejects_incomplete_generated_page_content(
    invalid_page: Page,
) -> None:
    document = wiki()
    invalid = replace(
        document,
        sections=(
            replace(
                document.sections[0],
                pages=(invalid_page, *document.sections[0].pages[1:]),
            ),
        ),
    )

    with pytest.raises(ValueError, match="generated page"):
        assemble_wiki(invalid)
