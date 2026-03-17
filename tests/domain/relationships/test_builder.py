from __future__ import annotations

from pathlib import Path
import sys

"""
Tests cho GraphBuilder.

Sử dụng tmp_path để tạo workspace nhỏ với vài file Python,
rồi verify rằng GraphBuilder build được IMPORTS edges đúng
dựa trên DependencyResolver hiện có.
"""
# Đảm bảo project root nằm trong sys.path để import domain/*
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domain.relationships.builder import GraphBuilder  # noqa: E402


def _write_file(path: Path, content: str) -> None:
    """Helper ghi file với nội dung cho test."""

    path.write_text(content, encoding="utf-8")


def test_builder_builds_import_edges_from_workspace(tmp_path: Path) -> None:
    """
    Kiểm tra GraphBuilder sử dụng DependencyResolver để tạo IMPORTS edges.
    """

    workspace = tmp_path

    # Tạo cấu trúc:
    #   a.py -> import b
    #   b.py -> import c
    #   c.py (no imports)
    a_py = workspace / "a.py"
    b_py = workspace / "b.py"
    c_py = workspace / "c.py"

    _write_file(a_py, "import b\n")
    _write_file(b_py, "import c\n")
    _write_file(c_py, "x = 1\n")

    builder = GraphBuilder(workspace_root=workspace)

    graph = builder.build(
        file_paths=[str(a_py), str(b_py), str(c_py)],
        existing_resolver=None,
        imports_max_depth=2,
    )

    # Normalize absolute paths để so sánh
    a_abs = str(a_py.resolve())
    b_abs = str(b_py.resolve())
    c_abs = str(c_py.resolve())

    # Edge từ a -> b và b -> c phải tồn tại
    related_from_a = graph.get_related_files_with_depth(a_abs, max_depth=2)
    assert b_abs in related_from_a
    assert c_abs in related_from_a
    # DependencyResolver có thể resolve transitive imports nên depth có thể là 1 hoặc 2
    assert related_from_a[b_abs] in (1, 2)
    assert related_from_a[c_abs] in (1, 2)

    # Đảm bảo graph đếm file/cạnh hợp lý
    assert graph.file_count() >= 2
    # Ít nhất có 1 cạnh imports trong graph này
    assert graph.edge_count() >= 1
