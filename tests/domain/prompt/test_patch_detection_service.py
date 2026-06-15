import time
import os
from domain.prompt.patch_detection_service import (
    PatchDetectionService,
)


def test_detects_search_replace_blocks() -> None:
    """Kiểm tra việc phát hiện các khối Search/Replace hợp lệ."""
    text = """
    Chào bạn, dưới đây là thay đổi tôi đề xuất:
<<<<<<< SEARCH main.py
def old():
    pass
=======
def new():
    return 1
>>>>>>> REPLACE
    """
    service = PatchDetectionService()
    result = service.detect(text)
    assert result.has_patches is True
    assert len(result.file_actions) == 1
    assert "main.py" in result.affected_files
    assert len(result.parse_errors) == 0


def test_detects_opx_blocks() -> None:
    """Kiểm tra việc phát hiện các khối OPX XML hợp lệ."""
    text = """
    <edit file="src/app.py" op="patch">
        <find>
<<<
def old():
    pass
>>>
        </find>
        <put>
<<<
def new():
    return 42
>>>
        </put>
    </edit>
    """
    service = PatchDetectionService()
    result = service.detect(text)
    assert result.has_patches is True
    assert len(result.file_actions) == 1
    assert "src/app.py" in result.affected_files
    assert len(result.parse_errors) == 0


def test_no_patches_returns_false() -> None:
    """Kiểm tra hội thoại thông thường không có patch trả về has_patches=False và không có lỗi."""
    text = "Chào bạn, hôm nay tôi có thể giúp gì cho bạn trong việc refactor dự án này?"
    service = PatchDetectionService()
    result = service.detect(text)
    assert result.has_patches is False
    assert len(result.file_actions) == 0
    assert len(result.affected_files) == 0
    assert len(result.parse_errors) == 0


def test_affected_files_populated_correctly() -> None:
    """Kiểm tra danh sách affected_files là đường dẫn tương đối, không trùng lặp và đúng thứ tự."""
    current_dir = os.getcwd()
    abs_path1 = os.path.join(current_dir, "src", "main.py")
    abs_path2 = os.path.join(current_dir, "src", "utils.py")

    text = f"""
    <edit file="{abs_path1}" op="remove" />
    <edit file="{abs_path2}" op="remove" />
    <edit file="{abs_path1}" op="remove" />
    """
    service = PatchDetectionService(workspace_root=current_dir)
    result = service.detect(text)

    assert result.has_patches is True
    assert len(result.file_actions) == 3
    # Phải chuyển thành relative path và loại bỏ trùng lặp (giữ thứ tự)
    assert result.affected_files == ["src/main.py", "src/utils.py"]


def test_parse_errors_captured() -> None:
    """Kiểm tra các lỗi cú pháp khi parse patch được capture trong parse_errors."""
    text = """
    <edit file="src/app.py" op="patch">
        <find>
<<<
def old():
    pass
>>>
    </edit>
    """
    service = PatchDetectionService()
    result = service.detect(text)
    # OPX bị thiếu thẻ đóng </find> sẽ tạo ra lỗi parse
    assert len(result.parse_errors) > 0


def test_performance_100kb_under_500ms() -> None:
    """Kiểm tra hiệu năng xử lý văn bản 100KB dưới 500ms."""
    # Giả lập văn bản lớn ~100KB chứa chat bình thường kèm 1 block patch
    base_text = (
        "Hệ thống AI đang phân tích mã nguồn và trả về kết quả.\n" * 1600
    )  # ~85KB
    patch_text = """
<<<<<<< SEARCH test_perf.py
def test_run():
    pass
=======
def test_run():
    print("performance check")
>>>>>>> REPLACE
    """
    full_text = base_text + patch_text + (base_text[:10000])  # ~100KB
    service = PatchDetectionService()

    start_time = time.time()
    result = service.detect(full_text)
    end_time = time.time()

    elapsed = end_time - start_time
    assert elapsed < 0.5  # Yêu cầu thời gian thực thi dưới 500ms
    assert result.has_patches is True
    assert "test_perf.py" in result.affected_files


def test_empty_string_input_no_crash() -> None:
    """Kiểm tra đầu vào chuỗi rỗng không làm crash ứng dụng."""
    service = PatchDetectionService()
    result = service.detect("")
    assert result.has_patches is False
    assert len(result.file_actions) == 0
    assert len(result.affected_files) == 0
    assert len(result.parse_errors) == 0


def test_none_like_input_handled() -> None:
    """Kiểm tra đầu vào None hoặc None-like strings (None, null) được xử lý an toàn."""
    service = PatchDetectionService()

    # Test None
    result = service.detect(None)  # type: ignore
    assert result.has_patches is False

    # Test "None" string
    result = service.detect("None")
    assert result.has_patches is False

    # Test "null" string
    result = service.detect("null")
    assert result.has_patches is False
