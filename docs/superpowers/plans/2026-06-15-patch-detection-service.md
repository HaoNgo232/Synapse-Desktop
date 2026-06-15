# PatchDetectionService Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Triển khai PatchDetectionService để phát hiện và phân tích các thay đổi file (patch) từ AI response text (hỗ trợ OPX và Search/Replace).

**Architecture:** Sử dụng trực tiếp hàm `parse_any_response` của `opx_parser` để phân tích cú pháp, map kết quả sang `PatchDetectionResult`, đồng thời lọc và chuẩn hóa `affected_files` thành danh sách các đường dẫn tương đối (relative path) độc nhất và giữ nguyên thứ tự xuất hiện gốc.

**Tech Stack:** Python 3, Pytest, Ruff (linter/formatter), Pyrefly (type checker).

---

### Task 1: Tạo file test với các test case rỗng (TDD Setup)

**Files:**
- Create: `tests/domain/prompt/test_patch_detection_service.py`

- [ ] **Step 1: Tạo file test và khai báo các signature test trống**

Tạo file `tests/domain/prompt/test_patch_detection_service.py` với nội dung định nghĩa cấu trúc test (body của các hàm tạm thời để trống bằng `pass`):

```python
import pytest

def test_detects_search_replace_blocks():
    """Kiểm tra việc phát hiện các khối Search/Replace hợp lệ."""
    pass

def test_detects_opx_blocks():
    """Kiểm tra việc phát hiện các khối OPX XML hợp lệ."""
    pass

def test_no_patches_returns_false():
    """Kiểm tra hội thoại thông thường không có patch trả về has_patches=False và không có lỗi."""
    pass

def test_affected_files_populated_correctly():
    """Kiểm tra danh sách affected_files là đường dẫn tương đối, không trùng lặp và đúng thứ tự."""
    pass

def test_parse_errors_captured():
    """Kiểm tra các lỗi cú pháp khi parse patch được capture trong parse_errors."""
    pass

def test_performance_100kb_under_500ms():
    """Kiểm tra hiệu năng xử lý văn bản 100KB dưới 500ms."""
    pass

def test_empty_string_input_no_crash():
    """Kiểm tra đầu vào chuỗi rỗng không làm crash ứng dụng."""
    pass

def test_none_like_input_handled():
    """Kiểm tra đầu vào None hoặc None-like strings (None, null) được xử lý an toàn."""
    pass
```

- [ ] **Step 2: Chạy pytest để đảm bảo các test rỗng chạy thành công (tất cả PASS)**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/prompt/test_patch_detection_service.py -v`
Expected: 8 passed

- [ ] **Step 3: Commit thiết lập TDD ban đầu**

```bash
git add tests/domain/prompt/test_patch_detection_service.py
git commit -m "test: setup initial empty tests for PatchDetectionService"
```

---

### Task 2: Cập nhật các test case thực tế và xác nhận chúng FAIL

**Files:**
- Modify: `tests/domain/prompt/test_patch_detection_service.py`

- [ ] **Step 1: Viết mã nguồn kiểm thử chi tiết cho toàn bộ các test case**

Thay thế toàn bộ nội dung file `tests/domain/prompt/test_patch_detection_service.py`:

```python
import time
import pytest
import os
from domain.prompt.patch_detection_service import PatchDetectionService, PatchDetectionResult

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
    base_text = "Hệ thống AI đang phân tích mã nguồn và trả về kết quả.\n" * 1600  # ~85KB
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
```

- [ ] **Step 2: Chạy pytest để đảm bảo các test case FAIL (do chưa import và triển khai class)**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/prompt/test_patch_detection_service.py -v`
Expected: FAIL (lỗi ImportError do chưa có class)

- [ ] **Step 3: Commit các test case thực tế**

```bash
git add tests/domain/prompt/test_patch_detection_service.py
git commit -m "test: write actual unit tests for PatchDetectionService"
```

---

### Task 3: Triển khai PatchDetectionService

**Files:**
- Create: `domain/prompt/patch_detection_service.py`

- [ ] **Step 1: Triển khai đầy đủ logic của PatchDetectionService**

Tạo file `domain/prompt/patch_detection_service.py` với mã nguồn hoàn chỉnh:

```python
import os
from dataclasses import dataclass, field
from typing import List, Optional, Set
from domain.prompt.opx_parser import (
    FileAction,
    parse_any_response,
    _looks_like_opx,
    _looks_like_search_replace,
)


@dataclass
class PatchDetectionResult:
    """
    Kết quả phân tích nhận diện patch từ AI response.

    Attributes:
        has_patches (bool): True nếu có ít nhất một file action hợp lệ được phân tích thành công.
        file_actions (List[FileAction]): Danh sách các file action được phân tích từ opx_parser.
        parse_errors (List[str]): Danh sách các lỗi cú pháp xảy ra khi cố gắng parse patch.
        affected_files (List[str]): Danh sách các đường dẫn tương đối, độc nhất của các file bị ảnh hưởng.
    """

    has_patches: bool
    file_actions: List[FileAction] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)


class PatchDetectionService:
    """
    Service phát hiện và trích xuất thông tin patch từ AI response text.
    """

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        """
        Khởi tạo service với thư mục gốc workspace tùy chọn.

        Args:
            workspace_root (Optional[str]): Thư mục gốc của workspace dùng để tính toán relative path.
        """
        self.workspace_root = workspace_root

    def detect(self, raw_text: str) -> PatchDetectionResult:
        """
        Phát hiện và parse các patch từ text thô của AI response.

        Hàm này sử dụng trực tiếp logic của opx_parser để nhận dạng và phân tích
        cú pháp định dạng OPX hoặc Search/Replace.

        Args:
            raw_text (str): Phản hồi thô từ AI.

        Returns:
            PatchDetectionResult: Kết quả phân tích chứa thông tin patch và lỗi cú pháp nếu có.
        """
        # 1. Guard clauses cho đầu vào trống hoặc None-like
        if raw_text is None:
            return PatchDetectionResult(has_patches=False)

        if not isinstance(raw_text, str):
            return PatchDetectionResult(has_patches=False)

        cleaned = raw_text.strip()
        if not cleaned or cleaned.lower() in ("none", "null"):
            return PatchDetectionResult(has_patches=False)

        # 2. Kiểm tra xem text có chứa cấu trúc patch hay không (tránh coi chat thường là lỗi parse)
        is_opx = _looks_like_opx(cleaned)
        is_sr = _looks_like_search_replace(cleaned)

        if not is_opx and not is_sr:
            # Hội thoại thông thường, không có ý định patch -> trả về kết quả trống, không có lỗi
            return PatchDetectionResult(has_patches=False)

        # 3. Phân tích cú pháp bằng opx_parser
        parse_result = parse_any_response(cleaned)

        file_actions = parse_result.file_actions
        has_patches = len(file_actions) > 0
        parse_errors = parse_result.errors

        # 4. Trích xuất affected_files (relative path, unique, giữ nguyên thứ tự)
        affected_files: List[str] = []
        seen_paths: Set[str] = set()

        for action in file_actions:
            path = action.path

            # Chuẩn hóa path thành relative path nếu là absolute path
            if os.path.isabs(path):
                root = self.workspace_root or os.getcwd()
                try:
                    rel_path = os.path.relpath(path, root)
                except Exception:
                    rel_path = path
            else:
                rel_path = path

            # Lọc trùng lặp nhưng giữ nguyên thứ tự xuất hiện gốc
            if rel_path not in seen_paths:
                seen_paths.add(rel_path)
                affected_files.append(rel_path)

        return PatchDetectionResult(
            has_patches=has_patches,
            file_actions=file_actions,
            parse_errors=parse_errors,
            affected_files=affected_files,
        )
```

- [ ] **Step 2: Đăng ký export lớp service trong `domain/prompt/__init__.py` (nếu cần)**

Kiểm tra xem file `domain/prompt/__init__.py` có export các component khác không. Nếu có, export `PatchDetectionService` và `PatchDetectionResult`.

- [ ] **Step 3: Chạy pytest để xác nhận toàn bộ test case PASS**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/prompt/test_patch_detection_service.py -v`
Expected: 8 passed

- [ ] **Step 4: Chạy format & linter bằng Ruff để chuẩn hóa code**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format domain/prompt/patch_detection_service.py tests/domain/prompt/test_patch_detection_service.py
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix domain/prompt/patch_detection_service.py tests/domain/prompt/test_patch_detection_service.py
```
Expected: Không có lỗi linter/formatter nào chưa được xử lý.

- [ ] **Step 5: Chạy type check bằng Pyrefly**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check`
Expected: PASS không có lỗi type check.

- [ ] **Step 6: Commit phần triển khai chính thức**

```bash
git add domain/prompt/patch_detection_service.py tests/domain/prompt/test_patch_detection_service.py
git commit -m "feat: implement PatchDetectionService and PatchDetectionResult with full TDD tests"
```
