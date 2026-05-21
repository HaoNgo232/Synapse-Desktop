import os
import sys
from pathlib import Path
import shutil

# Thêm workspace vào python path để import được các domain modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from infrastructure.filesystem.file_utils import scan_directory
from infrastructure.filesystem.ignore_engine import IgnoreEngine
from domain.codemap.symbol_extractor import extract_symbols
from domain.codemap.relationship_extractor import extract_relationships


def test_bug1_circular_symlinks():
    print("\n=== TEST BUG 1: Circular Symlinks / Infinite Recursion ===")
    # Tạo thư mục tạm bên trong workspace
    temp_dir = Path(PROJECT_ROOT) / "temp_symlink_test"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    try:
        sub_dir = temp_dir / "subdir"
        sub_dir.mkdir()

        # Tạo file bình thường
        (sub_dir / "file.txt").write_text("hello")

        # Tạo circular symlink: subdir/loop -> temp_dir
        loop_link = sub_dir / "loop"
        os.symlink(temp_dir, loop_link)

        print(f"Đã tạo circular symlink tại: {loop_link} -> {temp_dir}")
        print("Đang chạy scan_directory...")

        ignore_engine = IgnoreEngine()

        try:
            # Gọi scan_directory, hy vọng kích hoạt RecursionError hoặc OSError ELOOP
            result = scan_directory(temp_dir, ignore_engine, use_gitignore=False)
            print(
                "Lỗi: scan_directory chạy thành công mà không bị đệ quy vô hạn! (Có thể symlink đã bị bỏ qua ngoài ý muốn?)"
            )
        except (RecursionError, OSError) as e:
            print("Thành công kích hoạt lỗi! Phát hiện Exception mong đợi:")
            print(f"  {type(e).__name__}: {e}")
        except Exception as e:
            print(f"Phát hiện ngoại lệ khác: {type(e).__name__}: {e}")

    finally:
        # Dọn dẹp: Phải xoá symlink trước để tránh shutil.rmtree xoá đệ quy vô hạn
        try:
            if "loop_link" in locals() and loop_link.exists(follow_symlinks=False):
                loop_link.unlink()
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Lỗi khi dọn dẹp thư mục tạm: {e}")


def test_bug2_utf8_offset_mismatch():
    print("\n=== TEST BUG 2: UTF-8 Byte Offset vs Python Char Index ===")

    # File python mẫu chứa ký tự emoji và tiếng Việt có dấu nhiều byte.
    # Emoji '🌟' chiếm 4 bytes trong UTF-8.
    # Ký tự tiếng Việt 'ế' chiếm 2 bytes, 'ớ' chiếm 2 bytes.
    content = """# 🌟🌟🌟 Cảnh báo: File này chứa emoji
def xin_chào_thế_giới():
    print("Hello")
    đọc_sách()
"""
    file_path = "test_utf8.py"

    # 1. Test symbol signature extraction
    print("--- Trích xuất Symbols ---")
    symbols = extract_symbols(file_path, content)
    for sym in symbols:
        print(f"Symbol: {sym.name} ({sym.kind})")
        print(f"  Line: {sym.line_start} - {sym.line_end}")
        print(f"  Signature: {repr(sym.signature)}")

    # 2. Test relationship extraction (CALLS target)
    print("\n--- Trích xuất Relationships ---")
    # Để giả lập workspace_root, ta dùng thư mục hiện tại
    relationships = extract_relationships(file_path, content)
    for rel in relationships:
        print(
            f"Relationship: {rel.source} {rel.kind.value} {repr(rel.target)} (Line {rel.source_line})"
        )


def test_bug3_scope_matching_error():
    print(
        "\n=== TEST BUG 3: Scope Matching Error (Unsorted symbols when finding parent) ==="
    )

    content = """class SinhVien:
    def học_tập(self):
        pass

class GiaoVien:
    def giảng_dạy(self):
        pass
"""
    file_path = "test_scope.py"

    # Chúng ta sẽ xem tree-sitter captures trả về thế nào
    print("Đang chạy extract_symbols...")
    symbols = extract_symbols(file_path, content)

    print("Các symbols trích xuất được:")
    for sym in symbols:
        print(f"Symbol: {sym.name} ({sym.kind}), Parent: {sym.parent}")


if __name__ == "__main__":
    test_bug1_circular_symlinks()
    test_bug2_utf8_offset_mismatch()
    test_bug3_scope_matching_error()
