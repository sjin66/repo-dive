from __future__ import annotations

from pathlib import Path

from repo_dive.indexing.graph import RelationshipDirection, SymbolGraph
from repo_dive.indexing.store import IndexStore
from repo_dive.parsing.models import (
    ParseResult,
    Relationship,
    Symbol,
    create_relationship,
    create_symbol,
)
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
    path: str = "src/server.py",
    line: int,
) -> Symbol:
    return create_symbol(
        kind="class",
        name=name,
        qualified_name=qualified_name,
        path=path,
        start_line=line,
        end_line=line + 2,
    )


def graph_records() -> tuple[
    tuple[Symbol, Symbol, Symbol, Symbol], tuple[Relationship, ...]
]:
    server = symbol("HTTPServer", "pkg.HTTPServer", line=1)
    normalized = symbol("httpserver", "pkg.httpserver", line=10)
    client = symbol("Client", "pkg.Client", line=20)
    test_server = symbol(
        "HTTPServer",
        "tests.HTTPServer",
        path="tests/server_test.py",
        line=1,
    )
    relationships = (
        create_relationship(
            source_id=server.id,
            target_id=client.id,
            kind="calls",
            confidence=0.9,
            source="python_ast:src/server.py:4",
        ),
        create_relationship(
            source_id=client.id,
            target_id=normalized.id,
            kind="calls",
            confidence=0.8,
            source="python_ast:src/server.py:22",
        ),
        create_relationship(
            source_id=normalized.id,
            target_id=server.id,
            kind="calls",
            confidence=0.7,
            source="python_ast:src/server.py:12",
        ),
        create_relationship(
            source_id=server.id,
            target_id=normalized.id,
            kind="contains",
            confidence=1.0,
            source="python_ast:src/server.py:1",
        ),
    )
    return (server, normalized, client, test_server), relationships


def populate(store: IndexStore) -> tuple[Symbol, Symbol, Symbol, Symbol]:
    symbols, relationships = graph_records()
    store.replace_document(
        source_file("src/server.py"),
        ParseResult(symbols=symbols[:3], relationships=relationships),
    )
    store.replace_document(
        source_file("tests/server_test.py"),
        ParseResult(symbols=(symbols[3],)),
    )
    return symbols


def test_symbol_search_prioritizes_exact_then_normalized_matches(
    tmp_path: Path,
) -> None:
    with IndexStore.initialize(tmp_path / "index.sqlite3") as store:
        server, normalized, _, test_server = populate(store)
        graph = SymbolGraph(store)

        matches = graph.find_symbols("HTTPServer")

        assert matches == (server, test_server, normalized)
        assert graph.find_symbols("pkg.HTTPServer") == (server, normalized)
        assert graph.find_symbols(
            "HTTPServer",
            path="tests/server_test.py",
        ) == (test_server,)


def test_outgoing_cycle_traversal_is_stable_and_depth_bounded(
    tmp_path: Path,
) -> None:
    with IndexStore.initialize(tmp_path / "index.sqlite3") as store:
        server, normalized, client, _ = populate(store)
        graph = SymbolGraph(store)

        traversal = graph.neighbors(
            (server.id,),
            direction=RelationshipDirection.OUTGOING,
            depth=3,
            edge_kinds=("calls",),
            max_nodes=3,
            max_edges=4,
        )

        assert (
            graph.neighbors(
                (server.id,),
                direction=RelationshipDirection.OUTGOING,
                depth=3,
                edge_kinds=("calls",),
                max_nodes=3,
                max_edges=4,
            )
            == traversal
        )
        assert traversal.roots == (server,)
        assert {node.id for node in traversal.nodes} == {
            server.id,
            normalized.id,
            client.id,
        }
        assert {
            (edge.source.id, edge.target.id, edge.kind) for edge in traversal.edges
        } == {
            (server.id, client.id, "calls"),
            (client.id, normalized.id, "calls"),
            (normalized.id, server.id, "calls"),
        }
        assert traversal.truncated is False


def test_graph_filters_edges_and_preserves_endpoint_locations(
    tmp_path: Path,
) -> None:
    with IndexStore.initialize(tmp_path / "index.sqlite3") as store:
        server, normalized, _, _ = populate(store)
        graph = SymbolGraph(store)

        traversal = graph.neighbors(
            (server.id,),
            direction=RelationshipDirection.OUTGOING,
            depth=1,
            edge_kinds=("contains",),
            max_nodes=4,
            max_edges=4,
        )

        assert traversal.nodes == (server, normalized)
        assert len(traversal.edges) == 1
        edge = traversal.edges[0]
        assert edge.source.path == "src/server.py"
        assert edge.source.start_line == 1
        assert edge.target.path == "src/server.py"
        assert edge.target.start_line == 10
        assert edge.kind == "contains"
        assert edge.confidence == 1.0
        assert edge.provenance == "python_ast:src/server.py:1"


def test_graph_enforces_node_limit_and_supports_incoming_edges(
    tmp_path: Path,
) -> None:
    with IndexStore.initialize(tmp_path / "index.sqlite3") as store:
        server, normalized, client, _ = populate(store)
        graph = SymbolGraph(store)

        limited = graph.neighbors(
            (server.id,),
            direction=RelationshipDirection.OUTGOING,
            depth=3,
            edge_kinds=("calls",),
            max_nodes=2,
            max_edges=4,
        )
        incoming = graph.neighbors(
            (server.id,),
            direction=RelationshipDirection.INCOMING,
            depth=1,
            edge_kinds=("calls",),
            max_nodes=3,
            max_edges=4,
        )

        assert len(limited.nodes) == 2
        assert limited.nodes[0] == server
        assert limited.truncated is True
        assert incoming.nodes == (server, normalized)
        assert len(incoming.edges) == 1
        assert incoming.edges[0].source == normalized
        assert incoming.edges[0].target == server
        assert client not in incoming.nodes
