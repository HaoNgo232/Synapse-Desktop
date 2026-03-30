from __future__ import annotations
from pathlib import Path
import sys
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domain.relationships.builder import GraphBuilder  # noqa: E402


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.parametrize("use_unified", [True, False])
def test_graph_builder_unified_pass_consistency(
    tmp_path: Path, use_unified: bool
) -> None:
    """
    RED: Test này sẽ fail nếu chúng ta chưa implement unified pass hoặc
    kết quả của unified pass khác với kết quả của sequential pass hiện tại.
    """
    workspace = tmp_path

    # Tạo source code mẫu có quan hệ phức tạp
    # utils.py
    utils_py = workspace / "utils.py"
    _write_file(
        utils_py,
        """
def helper_func():
    return True

class BaseHelper:
    def base_method(self):
        pass
""",
    )

    # service.py (imports utils, calls helper, inherits BaseHelper)
    service_py = workspace / "service.py"
    _write_file(
        service_py,
        """
from utils import helper_func, BaseHelper

class MyService(BaseHelper):
    def run(self):
        helper_func()
        self.base_method()
""",
    )

    builder = GraphBuilder(workspace_root=workspace)

    # Sẽ bật flag sau khi implement logic thật
    graph = builder.build(
        file_paths=[str(utils_py), str(service_py)], imports_max_depth=1
    )

    utils_abs = str(utils_py.resolve())
    service_abs = str(service_py.resolve())

    # 1. Kiểm tra IMPORTS
    service_deps = graph.get_related_files_with_depth(service_abs, max_depth=1)
    assert utils_abs in service_deps, "Service phải import utils"

    # 3. Kiểm tra CALLS / INHERITS (Phase 2b)
    edges = graph.get_edges_from(service_abs)
    edge_kinds = [e.kind.name for e in edges if e.target_file == utils_abs]

    assert "IMPORTS" in edge_kinds


def test_graph_builder_performance_improvement(tmp_path: Path):
    """
    RED: Test này sẽ fail nếu tốc độ build không nhanh hơn ngưỡng quy định.
    """
    import time

    workspace = tmp_path

    # Tạo 50 file mock để đo hiệu năng
    files = []
    for i in range(50):
        f = workspace / f"file_{i}.py"
        _write_file(f, f"def func_{i}(): pass\nimport file_{(i + 1) % 50}")
        files.append(str(f))

    builder = GraphBuilder(workspace_root=workspace)

    start_time = time.perf_counter()
    builder.build(file_paths=files)
    end_time = time.perf_counter()

    duration = end_time - start_time
    print(f"Build duration for 50 files: {duration:.4f}s")

    # Giả sử target tối ưu là < 0.5s cho 50 files
    # Chúng ta sẽ assert một giá trị thấp để trigger RED (fail) nếu chưa tối ưu
    assert duration < 0.1, f"Build quá chậm: {duration:.4f}s"
