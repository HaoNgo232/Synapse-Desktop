"""
Unit tests cho Design Drift Detector.

Các test cases kiểm tra khả năng phát hiện drift (lệch thiết kế) khi sửa đổi file:
- Mức độ lệch thấp (LOW drift)
- Mức độ lệch trung bình (MEDIUM drift)
- Mức độ lệch cao (HIGH drift)
- Xử lý các đầu vào trống/None
"""

import pytest
from pathlib import Path
from domain.drift.drift_detector import detect_drift, DriftReport


def test_detect_drift_low_drift() -> None:
    """Kiểm tra trường hợp thay đổi đúng kế hoạch, không có cảnh báo nào (LOW drift)."""
    workspace = Path("/workspace")
    planned = ["src/main.py", "src/utils.py"]
    actual = ["src/main.py"]

    report = detect_drift(workspace, planned, actual)

    assert report.drift_score == "LOW"
    assert len(report.out_of_scope_files) == 0
    assert "Design Drift Score: LOW" in report.summary


def test_detect_drift_medium_drift() -> None:
    """Kiểm tra trường hợp sửa đổi ngoài scope nhưng ở mức độ vừa phải (MEDIUM drift)."""
    workspace = Path("/workspace")
    planned = ["src/main.py", "src/utils.py", "src/core.py", "src/network.py", "src/db.py"]
    # 2 files ngoài scope / 5 files planned = 0.4 (lớn hơn MEDIUM_SCOPE_RATIO là 0.2)
    actual = ["src/main.py", "src/extra.py", "src/helper.py"]

    report = detect_drift(workspace, planned, actual)

    assert report.drift_score == "MEDIUM"
    assert report.out_of_scope_files == ["src/extra.py", "src/helper.py"]


def test_detect_drift_high_drift() -> None:
    """Kiểm tra trường hợp sửa đổi ngoài scope quá nhiều (HIGH drift)."""
    workspace = Path("/workspace")
    planned = ["src/main.py"]
    # 1 file ngoài scope / 1 file planned = 1.0 (lớn hơn HIGH_SCOPE_RATIO là 0.5)
    actual = ["src/main.py", "src/extra.py"]

    report = detect_drift(workspace, planned, actual)

    assert report.drift_score == "HIGH"
    assert report.out_of_scope_files == ["src/extra.py"]


def test_detect_drift_coupling_and_api_changes() -> None:
    """Kiểm tra việc phát hiện tăng coupling và thay đổi public API."""
    workspace = Path("/workspace")
    planned = ["src/main.py"]
    actual = ["src/main.py"]

    pre_syms = {"src/main.py": ["foo", "bar"]}
    post_syms = {"src/main.py": ["foo", "baz"]}  # removed bar, added baz

    pre_deps = {"src/main.py": ["os"]}
    post_deps = {"src/main.py": ["os", "sys", "json", "math"]}  # tăng 3 imports (> threshold 2)

    report = detect_drift(
        workspace_root=workspace,
        planned_files=planned,
        actual_changed_files=actual,
        pre_edit_symbols=pre_syms,
        post_edit_symbols=post_syms,
        pre_edit_deps=pre_deps,
        post_edit_deps=post_deps,
    )

    assert "+ src/main.py::baz" in report.public_api_changes
    assert "- src/main.py::bar" in report.public_api_changes
    assert "src/main.py -> sys" in report.new_dependencies
    assert len(report.coupling_warnings) == 1
    assert "imports increased from 1 to 4" in report.coupling_warnings[0]


def test_detect_drift_empty_inputs() -> None:
    """Kiểm tra khi đầu vào trống hoặc None."""
    workspace = Path("/workspace")
    report = detect_drift(workspace, [], [])
    assert report.drift_score == "LOW"
    assert report.planned_files == []
    assert report.actual_changed_files == []
