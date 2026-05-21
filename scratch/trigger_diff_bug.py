import sys

# Thêm thư mục gốc của dự án vào sys.path để import các module domain
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from domain.diff.generator import generate_diff_lines


def test_diff_eof_bug():
    print("=== Test: Lỗi cảnh báo EOF và lệch dòng trong Diff ===")

    # Nội dung không có ký tự xuống dòng ở cuối file (EOF)
    old_content = "line1\nline2"
    new_content = "line1\nline2_modified"

    print("Đang tạo diff...")
    diff_lines = generate_diff_lines(old_content, new_content, "test.txt")

    print("\nCác dòng Diff đã parse:")
    for dl in diff_lines:
        old_no = str(dl.old_line_no) if dl.old_line_no is not None else " "
        new_no = str(dl.new_line_no) if dl.new_line_no is not None else " "
        print(f"[{dl.type.name}] (Old: {old_no:>2}, New: {new_no:>2}) | {dl.content}")

    # Kiểm tra xem bộ sinh diff hiện tại có hoạt động đúng với difflib.unified_diff không.
    # difflib.unified_diff của Python không sinh ra dòng cảnh báo "\\ No newline at end of file"
    # giống như git diff. Do đó, hàm này không bị lỗi lệch dòng khi dùng thuần Python,
    # nhưng kịch bản này giúp kiểm thử tính đúng đắn của số dòng được gán (Old: 2, New: 2).
    print(
        "\n✅ Kịch bản chạy thành công. Hãy kiểm tra các số dòng trên để đảm bảo căn lề chuẩn."
    )


if __name__ == "__main__":
    test_diff_eof_bug()
