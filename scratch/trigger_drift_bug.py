import sys
from pathlib import Path

# Thêm thư mục gốc của dự án vào sys.path để import các module domain
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from domain.drift.drift_detector import detect_drift


def test_drift_coupling_bug():
    print("=== Test: Lỗi cảnh báo Coupling (False Positive) trong Drift Detector ===")

    workspace = Path("/home/hao/Desktop/labs/Synapse-Desktop")
    planned_files = ["a.py"]
    actual_changed_files = ["a.py"]

    # Chúng ta KHÔNG truyền pre_edit_deps, nhưng truyền post_edit_deps chứa 3 imports
    pre_edit_deps = None
    post_edit_deps = {
        "a.py": ["shared.types", "domain.tokenization", "infrastructure.filesystem"]
    }

    print("Chạy detect_drift mà không có pre_edit_deps...")
    report = detect_drift(
        workspace_root=workspace,
        planned_files=planned_files,
        actual_changed_files=actual_changed_files,
        pre_edit_deps=pre_edit_deps,
        post_edit_deps=post_edit_deps,
    )

    print("\nKết quả Drift Report:")
    print(f"Drift Score: {report.drift_score}")
    print(f"Cảnh báo Coupling: {report.coupling_warnings}")

    # Xác nhận lỗi
    if report.coupling_warnings:
        print(
            "\n❌ XÁC NHẬN LỖI: Cảnh báo coupling vẫn được tạo ra mặc dù không có dữ liệu baseline (pre_edit_deps)!"
        )
        print(
            "Lỗi này khiến hệ thống báo cáo sai lệch rằng imports tăng từ 0 lên 3, dù không hề có sự tăng cơ học nào."
        )
    else:
        print(
            "\n✅ Thành công: Không có cảnh báo coupling nào được tạo khi pre_edit_deps là None."
        )


if __name__ == "__main__":
    test_drift_coupling_bug()
