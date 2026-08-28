from __future__ import annotations

from pathlib import Path

import pytest

from repo_dive.indexing.graph import SymbolGraph
from repo_dive.indexing.store import IndexStore
from repo_dive.parsing.models import (
    Chunk,
    ParseResult,
    Relationship,
    Symbol,
    create_chunk,
    create_relationship,
    create_symbol,
)
from repo_dive.retrieval.structural import search_structural
from repo_dive.scanner.models import FileRecord, ReadStatus, SourceFile


def source_file(path: str) -> SourceFile:
    return SourceFile(
        record=FileRecord(
            path=path,
            language="python",
            size_bytes=0,
            content_hash=f"hash:{path}",
            encoding="utf-8",
            status=ReadStatus.READ,
            skip_reason=None,
        ),
        text="",
    )


def symbol(
    name: str,
    qualified_name: str,
    *,
    kind: str = "function",
    line: int,
) -> Symbol:
    return create_symbol(
        kind=kind,
        name=name,
        qualified_name=qualified_name,
        path="src/graph.py",
        start_line=line,
        end_line=line + 2,
    )


def definition_chunk(item: Symbol) -> Chunk:
    return create_chunk(
        path=item.path,
        start_line=item.start_line,
        end_line=item.end_line,
        text=f"def {item.name}(): ...",
        symbol_id=item.id,
    )


def persist(
    store: IndexStore,
    *,
    symbols: tuple[Symbol, ...],
    chunks: tuple[Chunk, ...],
    relationships: tuple[Relationship, ...] = (),
) -> None:
    store.replace_document(
        source_file("src/graph.py"),
        ParseResult(
            symbols=symbols,
            chunks=chunks,
            relationships=relationships,
        ),
    )


def test_exact_qualified_definition_beats_normalized_and_reference_chunks(
    tmp_path: Path,
) -> None:
    target = symbol("Target", "pkg.Target", kind="class", line=1)
    normalized = symbol("target", "pkg.target", kind="class", line=10)
    holder = symbol("holder", "pkg.holder", line=20)
    reference = symbol("Target", "pkg.Target", kind="reference", line=21)
    chunks = (
        definition_chunk(target),
        definition_chunk(normalized),
        definition_chunk(holder),
    )

    with IndexStore.initialize(tmp_path / "index.sqlite3") as store:
        persist(
            store,
            symbols=(target, normalized, holder, reference),
            chunks=chunks,
        )

        hits = search_structural(
            "pkg.Target",
            graph=SymbolGraph(store),
            chunks=reversed(chunks),
            depth=0,
        )

    assert [hit.chunk.id for hit in hits] == [
        chunks[0].id,
        chunks[1].id,
        chunks[2].id,
    ]
    assert hits[0].structural_score > hits[1].structural_score
    assert hits[1].structural_score > hits[2].structural_score
    assert hits[0].reasons == ("symbol_match:qualified_name_exact:pkg.Target",)
    assert hits[1].reasons == ("symbol_match:qualified_name_normalized:pkg.target",)
    assert hits[2].reasons == ("symbol_match:qualified_name_exact:pkg.Target",)


def test_relationship_expansion_is_bounded_filtered_and_explainable(
    tmp_path: Path,
) -> None:
    root = symbol("Root", "pkg.Root", line=40)
    middle = symbol("Middle", "pkg.Middle", line=50)
    leaf = symbol("Leaf", "pkg.Leaf", line=60)
    caller = symbol("Caller", "pkg.Caller", line=70)
    low = symbol("Low", "pkg.Low", line=80)
    symbols = (root, middle, leaf, caller, low)
    chunks = tuple(definition_chunk(item) for item in symbols)
    relationships = (
        create_relationship(
            source_id=root.id,
            target_id=middle.id,
            kind="calls",
            confidence=0.9,
            source="fixture:40",
        ),
        create_relationship(
            source_id=middle.id,
            target_id=root.id,
            kind="calls",
            confidence=0.95,
            source="fixture:50",
        ),
        create_relationship(
            source_id=middle.id,
            target_id=leaf.id,
            kind="inherits",
            confidence=0.8,
            source="fixture:51",
        ),
        create_relationship(
            source_id=caller.id,
            target_id=root.id,
            kind="calls",
            confidence=0.85,
            source="fixture:70",
        ),
        create_relationship(
            source_id=root.id,
            target_id=low.id,
            kind="calls",
            confidence=0.4,
            source="fixture:41",
        ),
    )

    with IndexStore.initialize(tmp_path / "index.sqlite3") as store:
        persist(
            store,
            symbols=symbols,
            chunks=chunks,
            relationships=relationships,
        )
        graph = SymbolGraph(store)

        hits = search_structural(
            "pkg.Root",
            graph=graph,
            chunks=chunks,
            depth=2,
            max_nodes=10,
            max_edges=10,
            min_confidence=0.75,
        )
        depth_one = search_structural(
            "pkg.Root",
            graph=graph,
            chunks=chunks,
            depth=1,
            max_nodes=10,
            max_edges=10,
            min_confidence=0.75,
        )
        node_limited = search_structural(
            "pkg.Root",
            graph=graph,
            chunks=chunks,
            depth=5,
            max_nodes=2,
            max_edges=10,
            min_confidence=0.75,
        )

    hit_by_symbol_id = {hit.chunk.symbol_id: hit for hit in hits}
    assert set(hit_by_symbol_id) == {root.id, middle.id, leaf.id, caller.id}
    assert len(hits) == len({hit.chunk.id for hit in hits})
    assert (
        hit_by_symbol_id[root.id].structural_score
        > hit_by_symbol_id[middle.id].structural_score
    )
    assert (
        hit_by_symbol_id[middle.id].structural_score
        > hit_by_symbol_id[leaf.id].structural_score
    )
    assert "fixture:40" in hit_by_symbol_id[middle.id].reasons[0]
    assert "calls[confidence=0.900" in hit_by_symbol_id[middle.id].reasons[0]
    assert "fixture:51" in hit_by_symbol_id[leaf.id].reasons[0]
    assert "inherits[confidence=0.800" in hit_by_symbol_id[leaf.id].reasons[0]
    assert "<-calls[confidence=0.850" in hit_by_symbol_id[caller.id].reasons[0]
    assert leaf.id not in {hit.chunk.symbol_id for hit in depth_one}
    assert len(node_limited) <= 2


def test_result_and_input_boundaries_are_predictable(tmp_path: Path) -> None:
    root = symbol("Root", "pkg.Root", line=1)
    chunks = (definition_chunk(root),)

    with IndexStore.initialize(tmp_path / "index.sqlite3") as store:
        persist(store, symbols=(root,), chunks=chunks)
        graph = SymbolGraph(store)

        assert search_structural("", graph=graph, chunks=chunks) == ()
        assert (
            search_structural(
                "pkg.Root",
                graph=graph,
                chunks=chunks,
                max_results=0,
            )
            == ()
        )
        with pytest.raises(ValueError, match="min_confidence"):
            search_structural(
                "pkg.Root",
                graph=graph,
                chunks=chunks,
                min_confidence=1.1,
            )


def test_low_confidence_edges_do_not_consume_the_node_budget(tmp_path: Path) -> None:
    root = symbol("Root", "pkg.Root", line=40)
    high = symbol("Middle", "pkg.Middle", line=50)
    low = symbol("Low", "pkg.Low", line=80)
    assert low.id < high.id
    symbols = (root, high, low)
    chunks = tuple(definition_chunk(item) for item in symbols)
    relationships = (
        create_relationship(
            source_id=root.id,
            target_id=low.id,
            kind="calls",
            confidence=0.4,
            source="fixture:low",
        ),
        create_relationship(
            source_id=root.id,
            target_id=high.id,
            kind="calls",
            confidence=0.9,
            source="fixture:high",
        ),
    )

    with IndexStore.initialize(tmp_path / "index.sqlite3") as store:
        persist(
            store,
            symbols=symbols,
            chunks=chunks,
            relationships=relationships,
        )

        hits = search_structural(
            "pkg.Root",
            graph=SymbolGraph(store),
            chunks=chunks,
            depth=1,
            max_nodes=2,
            max_edges=2,
            min_confidence=0.75,
        )

    assert {hit.chunk.symbol_id for hit in hits} == {root.id, high.id}
