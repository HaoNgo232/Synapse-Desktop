from __future__ import annotations

from domain.relationships import Edge, EdgeKind, FileNode

"""
Tests cho domain/relationships/types.py
"""


def test_edge_creation() -> None:
    """Edge có thể được tạo với các thuộc tính cơ bản."""
    edge = Edge(
        source_file="/a.py",
        target_file="/b.py",
        kind=EdgeKind.IMPORTS,
    )
    assert edge.source_file == "/a.py"
    assert edge.target_file == "/b.py"
    assert edge.kind == EdgeKind.IMPORTS


def test_edge_with_metadata() -> None:
    """Edge có thể chứa metadata."""
    edge = Edge(
        source_file="/a.py",
        target_file="/b.py",
        kind=EdgeKind.CALLS,
        metadata={"symbol": "process", "line": 42},
    )
    assert edge.metadata is not None
    assert edge.metadata["symbol"] == "process"
    assert edge.metadata["line"] == 42


def test_edge_is_frozen() -> None:
    """Edge là immutable (frozen dataclass)."""
    edge = Edge("/a.py", "/b.py", EdgeKind.IMPORTS)
    try:
        edge.source_file = "/c.py"  # type: ignore
        assert False, "Should raise FrozenInstanceError"
    except Exception:
        pass


def test_edge_equality() -> None:
    """Hai edges giống nhau phải equal."""
    edge1 = Edge("/a.py", "/b.py", EdgeKind.IMPORTS)
    edge2 = Edge("/a.py", "/b.py", EdgeKind.IMPORTS)
    assert edge1 == edge2


def test_edge_hashing() -> None:
    """Edges có thể dùng làm dict keys."""
    edge1 = Edge("/a.py", "/b.py", EdgeKind.IMPORTS)
    edge2 = Edge("/a.py", "/b.py", EdgeKind.IMPORTS)
    edge_set = {edge1, edge2}
    assert len(edge_set) == 1


def test_file_node_creation() -> None:
    """FileNode có thể được tạo với edges."""
    node = FileNode(file_path="/a.py")
    assert node.file_path == "/a.py"
    assert node.edges_out == []
    assert node.edges_in == []


def test_file_node_can_store_edges() -> None:
    """FileNode có thể lưu trữ edges."""
    node = FileNode(file_path="/a.py")
    edge = Edge("/a.py", "/b.py", EdgeKind.IMPORTS)
    node.edges_out.append(edge)
    assert len(node.edges_out) == 1
    assert node.edges_out[0] == edge


def test_edge_kind_enum_values() -> None:
    """EdgeKind có đủ các giá trị cần thiết."""
    assert EdgeKind.IMPORTS.value == "imports"
    assert EdgeKind.CALLS.value == "calls"
    assert EdgeKind.INHERITS.value == "inherits"
