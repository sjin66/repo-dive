from __future__ import annotations

from repo_dive.knowledge_map.resolution import resolve_python_references
from repo_dive.parsing.models import create_relationship, create_symbol


def test_resolution_preserves_ambiguity_instead_of_selecting_a_winner() -> None:
    source = create_symbol(
        kind="function",
        name="main",
        qualified_name="app.main",
        path="app.py",
        start_line=1,
        end_line=2,
    )
    target = create_symbol(
        kind="reference",
        name="run",
        qualified_name="run",
        path="app.py",
        start_line=2,
        end_line=2,
    )
    candidates = tuple(
        create_symbol(
            kind="function",
            name="run",
            qualified_name=f"pkg{index}.run",
            path=f"pkg{index}.py",
            start_line=1,
            end_line=1,
        )
        for index in range(2)
    )
    relationship = create_relationship(
        source_id=source.id,
        target_id=target.id,
        kind="calls",
        confidence=0.75,
        provenance="python_ast",
        path="app.py",
        start_line=2,
        end_line=2,
        occurrence_discriminator=(1, 4, 0),
    )

    result = resolve_python_references(
        (*candidates, source, target), (relationship,), candidate_budget=8
    )

    assert result.resolutions[0].status == "ambiguous"
    assert len(result.resolutions[0].candidate_symbol_ids) == 2
    assert result.relationships == (relationship,)
