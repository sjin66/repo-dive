from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from repo_dive.errors import RepositoryError
from repo_dive.knowledge_map.evidence import plan_scope_evidence
from repo_dive.knowledge_map.models import (
    KnowledgeMapArtifact,
    RetrievalParameters,
    ScopeContract,
    ScopeKind,
)
from repo_dive.parsing.models import create_chunk, create_symbol


@pytest.mark.parametrize("scope_kind", ["cluster", "flow", "tour"])
def test_scope_plan_preserves_anchor_order_and_stable_fallback(
    scope_kind: str,
) -> None:
    definition = create_symbol(
        kind="function",
        name="run",
        qualified_name="pkg.app.run",
        path="pkg/app.py",
        start_line=3,
        end_line=4,
    )
    reference = create_symbol(
        kind="reference",
        name="missing",
        qualified_name="missing",
        path="pkg/app.py",
        start_line=8,
        end_line=8,
    )
    definition_chunk = create_chunk(
        path="pkg/app.py",
        start_line=3,
        end_line=4,
        text="def run():\n    return 1\n",
        symbol_id=definition.id,
    )
    later_chunk = create_chunk(
        path="pkg/z.py",
        start_line=1,
        end_line=1,
        text="VALUE = 1\n",
    )
    nodes = (
        SimpleNamespace(
            id="repository:one",
            kind="repository",
            name="repository",
            path=None,
            parent_id=None,
            parser_symbol_id=None,
        ),
        SimpleNamespace(
            id="module:pkg",
            kind="module",
            name="pkg",
            path=None,
            parent_id="repository:one",
            parser_symbol_id=None,
        ),
        SimpleNamespace(
            id="file:app",
            kind="file",
            name="app.py",
            path="pkg/app.py",
            parent_id="module:pkg",
            parser_symbol_id=None,
        ),
        SimpleNamespace(
            id="file:z",
            kind="file",
            name="z.py",
            path="pkg/z.py",
            parent_id="module:pkg",
            parser_symbol_id=None,
        ),
        SimpleNamespace(
            id="symbol:definition",
            kind="symbol",
            name="run",
            path="pkg/app.py",
            parent_id="file:app",
            parser_symbol_id=definition.id,
        ),
        SimpleNamespace(
            id="symbol:reference",
            kind="symbol",
            name="missing",
            path="pkg/app.py",
            parent_id="file:app",
            parser_symbol_id=reference.id,
        ),
    )
    contract = ScopeContract.create(
        scope_id=f"{scope_kind}:one",
        scope_kind=cast(ScopeKind, scope_kind),
        allowed_fact_node_ids=tuple(item.id for item in nodes),
        required_anchor_fact_node_ids=(
            "symbol:definition",
            "symbol:reference",
            "module:pkg",
        ),
        allowed_record_kinds=("concept",),
        allowed_claim_kinds=("label",),
    )
    artifact = cast(
        KnowledgeMapArtifact,
        SimpleNamespace(scope_contracts=(contract,), nodes=nodes),
    )
    parameters = RetrievalParameters(
        10,
        "weighted_rrf",
        60,
        (("lexical", 1.0),),
        0.8,
    )

    first = plan_scope_evidence(
        artifact,
        contract.scope_id,
        chunks=(later_chunk, definition_chunk),
        symbols=(reference, definition),
        retrieval_parameters=parameters,
    )
    second = plan_scope_evidence(
        artifact,
        contract.scope_id,
        chunks=(definition_chunk, later_chunk),
        symbols=(definition, reference),
        retrieval_parameters=parameters,
    )

    assert first == second
    assert tuple(item.chunk.id for item in first.required_chunks) == (
        definition_chunk.id,
    )
    assert first.required_chunks[0].anchor_fact_node_ids == (
        "symbol:definition",
        "symbol:reference",
        "module:pkg",
    )


def test_scope_plan_reports_unavailable_anchor_without_capacity_details() -> None:
    node = SimpleNamespace(
        id="file:empty",
        kind="file",
        name="empty.py",
        path="empty.py",
        parent_id="module:root",
        parser_symbol_id=None,
    )
    contract = ScopeContract.create(
        scope_id="cluster:empty",
        scope_kind="cluster",
        allowed_fact_node_ids=(node.id,),
        required_anchor_fact_node_ids=(node.id,),
        allowed_record_kinds=("concept",),
        allowed_claim_kinds=("summary",),
    )
    artifact = cast(
        KnowledgeMapArtifact,
        SimpleNamespace(scope_contracts=(contract,), nodes=(node,)),
    )
    parameters = RetrievalParameters(
        10,
        "weighted_rrf",
        60,
        (("lexical", 1.0),),
        0.8,
    )

    with pytest.raises(RepositoryError) as exc_info:
        plan_scope_evidence(
            artifact,
            contract.scope_id,
            chunks=(),
            symbols=(),
            retrieval_parameters=parameters,
        )

    assert exc_info.value.code == "knowledge_map_evidence_unavailable"
    assert exc_info.value.details == {
        "anchor_fact_node_id": node.id,
        "recovery_action": "make_source_indexable_or_select_scope",
        "retry_mode": "after_recovery",
        "scope_id": contract.scope_id,
    }
