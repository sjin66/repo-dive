from __future__ import annotations

from dataclasses import replace

import pytest

from repo_dive.parsing.models import Chunk, create_chunk
from repo_dive.retrieval.fusion import FusionParameters, fuse_hits
from repo_dive.retrieval.lexical import LexicalHit
from repo_dive.retrieval.structural import StructuralHit


def chunk(
    path: str,
    start_line: int,
    end_line: int,
    text: str,
    *,
    symbol_id: str | None = None,
) -> Chunk:
    return create_chunk(
        path=path,
        start_line=start_line,
        end_line=end_line,
        text=text,
        symbol_id=symbol_id,
    )


def lexical(item: Chunk, score: float, *terms: str) -> LexicalHit:
    return LexicalHit(chunk=item, lexical_score=score, matched_terms=terms)


def structural(item: Chunk, score: float, *reasons: str) -> StructuralHit:
    return StructuralHit(chunk=item, structural_score=score, reasons=reasons)


def test_weighted_rrf_records_parameters_and_does_not_invent_missing_ranks() -> None:
    shared = chunk("src/shared.py", 1, 3, "def shared(): ...", symbol_id="shared")
    lexical_only = chunk("src/lexical.py", 1, 2, "lexical evidence")
    structural_only = chunk(
        "src/structural.py",
        4,
        8,
        "def related(): ...",
        symbol_id="related",
    )
    parameters = FusionParameters(
        rrf_k=10,
        lexical_weight=2.0,
        structural_weight=3.0,
    )

    result = fuse_hits(
        lexical_hits=(
            lexical(shared, 9.0, "shared"),
            lexical(lexical_only, 4.0, "evidence"),
        ),
        structural_hits=(
            structural(shared, 1.0, "symbol_match:shared"),
            structural(structural_only, 0.5, "relationship_path:shared->related"),
        ),
        parameters=parameters,
    )

    assert result.metadata.strategy == "weighted_rrf"
    assert result.metadata.rrf_k == 10
    assert result.metadata.channel_weights == (
        ("lexical", 2.0),
        ("structural", 3.0),
    )
    assert result.metadata.overlap_threshold == pytest.approx(0.8)

    by_id = {hit.chunk.id: hit for hit in result.hits}
    assert by_id[shared.id].fused_score == pytest.approx(2 / 11 + 3 / 11)
    assert by_id[lexical_only.id].fused_score == pytest.approx(2 / 12)
    assert by_id[structural_only.id].fused_score == pytest.approx(3 / 12)
    assert by_id[lexical_only.id].structural_score is None
    assert by_id[structural_only.id].lexical_score is None
    assert by_id[shared.id].vector_score is None
    assert "lexical_match:shared" in by_id[shared.id].reasons
    assert "symbol_match:shared" in by_id[shared.id].reasons
    assert any(
        reason.startswith("rrf:lexical:rank=1") for reason in by_id[shared.id].reasons
    )
    assert any(
        reason.startswith("rrf:structural:rank=1")
        for reason in by_id[shared.id].reasons
    )


def test_exact_chunk_id_is_merged_across_channels_and_conflicts_are_rejected() -> None:
    item = chunk("src/service.py", 7, 9, "def serve(): ...", symbol_id="serve")

    result = fuse_hits(
        lexical_hits=(lexical(item, 2.5, "serve"),),
        structural_hits=(structural(item, 0.9, "symbol_match:serve"),),
    )

    assert len(result.hits) == 1
    assert result.hits[0].lexical_score == 2.5
    assert result.hits[0].structural_score == 0.9

    conflicting = replace(item, text="different text")
    with pytest.raises(ValueError, match="conflicting Chunks"):
        fuse_hits(
            lexical_hits=(lexical(item, 2.5, "serve"),),
            structural_hits=(structural(conflicting, 0.9, "symbol_match:serve"),),
        )


def test_overlap_dedup_prefers_informative_evidence_but_preserves_symbols() -> None:
    wrapper = chunk(
        "src/service.py",
        1,
        12,
        "class Service:\n    helper = 1\n",
    )
    definition = chunk(
        "src/service.py",
        3,
        8,
        "    def run(self):\n        return self.helper\n",
        symbol_id="Service.run",
    )
    alternate_symbol = chunk(
        "src/service.py",
        4,
        9,
        "    def stop(self):\n        return None\n",
        symbol_id="Service.stop",
    )

    result = fuse_hits(
        lexical_hits=(lexical(wrapper, 10.0, "service"),),
        structural_hits=(
            structural(definition, 0.8, "symbol_match:Service.run"),
            structural(alternate_symbol, 0.7, "symbol_match:Service.stop"),
        ),
    )

    assert {hit.chunk.id for hit in result.hits} == {
        definition.id,
        alternate_symbol.id,
    }


def test_overlap_dedup_uses_content_size_for_the_same_symbol() -> None:
    concise = chunk(
        "src/service.py",
        20,
        24,
        "def run():\n    return work()\n",
        symbol_id="run",
    )
    detailed = chunk(
        "src/service.py",
        20,
        25,
        "def run():\n    value = prepare()\n    return work(value)\n",
        symbol_id="run",
    )

    result = fuse_hits(
        lexical_hits=(lexical(concise, 9.0, "run"),),
        structural_hits=(structural(detailed, 0.4, "symbol_match:run"),),
    )

    assert [hit.chunk.id for hit in result.hits] == [detailed.id]


def test_channel_hit_order_does_not_change_ranking_or_deduplication() -> None:
    first = chunk("a.py", 1, 2, "alpha")
    second = chunk("b.py", 1, 2, "beta")
    overlapping = chunk("a.py", 1, 3, "alpha with more context")
    lexical_hits = (
        lexical(second, 1.0, "beta"),
        lexical(first, 1.0, "alpha"),
    )
    structural_hits = (
        structural(overlapping, 0.5, "file_neighbor:a.py"),
        structural(second, 0.5, "symbol_match:beta"),
    )

    forward = fuse_hits(
        lexical_hits=lexical_hits,
        structural_hits=structural_hits,
    )
    reversed_inputs = fuse_hits(
        lexical_hits=tuple(reversed(lexical_hits)),
        structural_hits=tuple(reversed(structural_hits)),
    )

    assert reversed_inputs == forward


def test_limits_and_parameters_are_validated() -> None:
    item = chunk("a.py", 1, 1, "alpha")
    hit = lexical(item, 1.0, "alpha")

    assert fuse_hits(lexical_hits=(hit,), max_results=0).hits == ()
    with pytest.raises(ValueError, match="max_results"):
        fuse_hits(lexical_hits=(hit,), max_results=-1)
    with pytest.raises(ValueError, match="rrf_k"):
        FusionParameters(rrf_k=-1)
    with pytest.raises(ValueError, match="channel weight"):
        FusionParameters(lexical_weight=0.0, structural_weight=0.0)
    with pytest.raises(ValueError, match="overlap_threshold"):
        FusionParameters(overlap_threshold=1.1)
