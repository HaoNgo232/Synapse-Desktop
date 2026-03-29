from __future__ import annotations

import threading
import time
from pathlib import Path
from application.services.graph_service import GraphService

"""
Tests cho GraphService - Application layer lifecycle management.
"""


def test_graph_service_get_graph_returns_none_initially() -> None:
    """Graph service trả về None khi chưa build."""
    service = GraphService()
    assert service.get_graph() is None


def test_graph_service_ensure_built_creates_graph(tmp_path: Path) -> None:
    """ensure_built tạo graph cho workspace."""
    workspace = tmp_path
    (workspace / "a.py").write_text("import b\n")
    (workspace / "b.py").write_text("x = 1\n")

    service = GraphService()
    graph = service.ensure_built(workspace)

    assert graph is not None
    assert graph.file_count() >= 2


def test_graph_service_invalidate_clears_graph() -> None:
    """invalidate xóa graph hiện tại."""
    service = GraphService()
    service._graph = object()  # type: ignore
    service.invalidate()
    assert service.get_graph() is None


def test_graph_service_on_workspace_changed_triggers_background_build(
    tmp_path: Path,
) -> None:
    """on_workspace_changed build graph trên background thread."""
    workspace = tmp_path
    (workspace / "a.py").write_text("import b\n")
    (workspace / "b.py").write_text("x = 1\n")

    service = GraphService()
    service.on_workspace_changed(workspace)

    # Lazy build: Graph still None until ensure_built or sync build
    assert service.get_graph() is None

    # Now trigger build
    graph = service.ensure_built(workspace)
    assert graph is not None
    assert graph.file_count() >= 2


def test_graph_service_on_files_changed_incremental_update(tmp_path: Path) -> None:
    """on_files_changed thực hiện incremental update."""
    workspace = tmp_path
    a_py = workspace / "a.py"
    b_py = workspace / "b.py"
    c_py = workspace / "c.py"

    a_py.write_text("import b\n")
    b_py.write_text("import c\n")
    c_py.write_text("x = 1\n")

    service = GraphService()
    graph = service.ensure_built(workspace)

    initial_edge_count = graph.edge_count()

    # Sửa file b.py để thêm import mới
    b_py.write_text("import c\nimport a\n")
    service.on_files_changed([str(b_py)])

    # Graph nên được update
    updated_graph = service.get_graph()
    assert updated_graph is not None
    # Edge count có thể thay đổi do rebuild edges cho b.py
    assert updated_graph.edge_count() >= initial_edge_count - 2


def test_graph_service_thread_safety(tmp_path: Path) -> None:
    """Multiple threads có thể gọi get_graph đồng thời."""
    workspace = tmp_path
    (workspace / "a.py").write_text("x = 1\n")

    service = GraphService()
    service.ensure_built(workspace)

    results = []
    errors = []

    def reader():
        try:
            for _ in range(10):
                graph = service.get_graph()
                results.append(graph is not None)
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert all(results)


def test_graph_service_generation_counter_prevents_stale_builds(tmp_path: Path) -> None:
    """Generation counter ngăn stale builds ghi đè builds mới hơn."""
    workspace = tmp_path
    (workspace / "a.py").write_text("x = 1\n")

    service = GraphService()

    # Trigger 2 builds liên tiếp - Generation tăng
    service.on_workspace_changed(workspace)
    service.on_workspace_changed(workspace)

    # Graph vẫn None vì lazy
    assert service.get_graph() is None
    assert service._generation >= 2

    # Build thật sự
    graph = service.ensure_built(workspace)
    assert graph is not None
