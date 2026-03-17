from __future__ import annotations

import sys
from pathlib import Path

"""
Tests cho RelationshipGraph ở mức unit.

Các test này đảm bảo:
- Thêm cạnh vào graph hoạt động đúng
- BFS theo depth cho ra kết quả và depth chính xác
- Lọc theo EdgeKind hoạt động đúng
- Không bị loop với đồ thị có chu trình
"""
# Đảm bảo project root nằm trong sys.path để import domain/*
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domain.relationships import Edge, EdgeKind, RelationshipGraph  # noqa: E402


def test_add_edge_and_counts() -> None:
    """Kiểm tra thêm cạnh và đếm số file/số cạnh."""

    graph = RelationshipGraph()

    edge1 = Edge(
        source_file="/a.py",
        target_file="/b.py",
        kind=EdgeKind.IMPORTS,
    )
    edge2 = Edge(
        source_file="/a.py",
        target_file="/c.py",
        kind=EdgeKind.IMPORTS,
    )

    graph.add_edge(edge1)
    graph.add_edge(edge2)

    assert graph.edge_count() == 2
    assert graph.file_count() == 3


def test_get_related_files_depth_1() -> None:
    """Kiểm tra BFS depth=1 chỉ trả neighbors trực tiếp."""

    graph = RelationshipGraph()

    graph.add_edge(Edge("/a.py", "/b.py", EdgeKind.IMPORTS))
    graph.add_edge(Edge("/b.py", "/c.py", EdgeKind.IMPORTS))

    related = graph.get_related_files("/a.py", max_depth=1)

    assert "/b.py" in related
    assert "/c.py" not in related


def test_get_related_files_depth_2() -> None:
    """Kiểm tra BFS depth=2 trả cả neighbors bậc 2."""

    graph = RelationshipGraph()

    graph.add_edge(Edge("/a.py", "/b.py", EdgeKind.IMPORTS))
    graph.add_edge(Edge("/b.py", "/c.py", EdgeKind.IMPORTS))

    related_with_depth = graph.get_related_files_with_depth("/a.py", max_depth=2)

    assert related_with_depth == {
        "/b.py": 1,
        "/c.py": 2,
    }


def test_get_related_files_edge_kind_filter() -> None:
    """Kiểm tra filter theo EdgeKind chỉ đi qua loại cạnh mong muốn."""

    graph = RelationshipGraph()

    graph.add_edge(Edge("/a.py", "/b.py", EdgeKind.IMPORTS))
    graph.add_edge(Edge("/b.py", "/c.py", EdgeKind.CALLS))

    # Chỉ IMPORTS: không đi tiếp qua CALLS
    only_imports = graph.get_related_files(
        "/a.py", max_depth=3, edge_kinds={EdgeKind.IMPORTS}
    )
    assert "/b.py" in only_imports
    assert "/c.py" not in only_imports

    # IMPORTS + CALLS: đi hết chuỗi
    all_edges = graph.get_related_files(
        "/a.py", max_depth=3, edge_kinds={EdgeKind.IMPORTS, EdgeKind.CALLS}
    )
    assert "/c.py" in all_edges


def test_circular_dependencies_do_not_infinite_loop() -> None:
    """Đảm bảo đồ thị có chu trình không gây loop vô hạn."""

    graph = RelationshipGraph()

    graph.add_edge(Edge("/a.py", "/b.py", EdgeKind.IMPORTS))
    graph.add_edge(Edge("/b.py", "/c.py", EdgeKind.IMPORTS))
    graph.add_edge(Edge("/c.py", "/a.py", EdgeKind.IMPORTS))

    related = graph.get_related_files("/a.py", max_depth=5)

    # Tất cả nodes khác A đều reachable nhưng không bị loop
    assert related == {"/b.py", "/c.py"}
