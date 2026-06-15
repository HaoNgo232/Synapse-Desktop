# Apply Tab Auto-Detection Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nâng cấp tab Apply để hỗ trợ luồng tự động nhận diện patch, hiển thị tóm tắt trực quan và kiểm soát trạng thái nút Apply Changes.

**Architecture:** Sử dụng `PatchDetectionService` tích hợp trực tiếp vào lớp `ApplyViewQt`, liên kết tín hiệu `textChanged` của textarea với cơ chế debounce 800ms bằng `QTimer`. Cập nhật trạng thái `self._apply_btn` (kích hoạt/vô hiệu hóa) và `self._summary_label` (tóm tắt/lỗi/thành công) một cách đồng bộ.

**Tech Stack:** Python 3, PySide6, Pytest, Pytest-qt, Ruff, Pyrefly.

---

### Task 1: Thiết lập TDD - Tạo file kiểm thử với các test rỗng

**Files:**
- Create: `tests/presentation/test_apply_tab_upgrade.py`

- [ ] **Step 1: Tạo cấu trúc test file rỗng**

Tạo file `tests/presentation/test_apply_tab_upgrade.py` định nghĩa các phương thức kiểm thử (nội dung dùng `pass`):

```python
import pytest

def test_no_duplicate_textarea_in_apply_tab(qtbot) -> None:
    """Kiểm tra chỉ có đúng một textarea trong Apply View."""
    pass

def test_detection_triggers_after_800ms_debounce(qtbot) -> None:
    """Kiểm tra tính năng tự động nhận diện được kích hoạt sau 800ms debounce."""
    pass

def test_apply_button_disabled_without_valid_patches(qtbot) -> None:
    """Nút Apply Changes bị disable khi không chứa patch hợp lệ."""
    pass

def test_apply_button_enabled_with_valid_patches(qtbot) -> None:
    """Nút Apply Changes được enable khi chứa patch hợp lệ."""
    pass

def test_summary_label_shows_filenames(qtbot) -> None:
    """Summary label hiển thị đúng số lượng thay đổi, số file và danh sách file."""
    pass

def test_summary_label_hidden_when_text_empty(qtbot) -> None:
    """Summary label tự động ẩn đi khi textarea trống."""
    pass

def test_paste_clipboard_button_fills_textarea(qtbot) -> None:
    """Verify việc paste clipboard chèn text vào textarea và kích hoạt detect."""
    pass

def test_textarea_clears_after_successful_apply(qtbot) -> None:
    """Textarea được dọn sạch sau khi áp dụng patch thành công."""
    pass

def test_summary_shows_success_after_apply(qtbot) -> None:
    """Nhãn tóm tắt hiển thị thông báo thành công sau khi apply."""
    pass
```

- [ ] **Step 2: Chạy pytest xác nhận các test rỗng PASS**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_apply_tab_upgrade.py -v`
Expected: 9 passed

- [ ] **Step 3: Commit**

```bash
git add tests/presentation/test_apply_tab_upgrade.py
git commit -m "test: setup TDD structure for Apply tab upgrade"
```

---

### Task 2: Cập nhật các Test Case thực tế và xác nhận chúng FAIL

**Files:**
- Modify: `tests/presentation/test_apply_tab_upgrade.py`

- [ ] **Step 1: Viết nội dung kiểm thử chi tiết sử dụng pytest-qt**

Ghi đè nội dung file `tests/presentation/test_apply_tab_upgrade.py` bằng các test case thực tế:

```python
import os
import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QPushButton, QLabel, QApplication
from presentation.views.apply.apply_view_qt import ApplyViewQt

def test_no_duplicate_textarea_in_apply_tab(qtbot) -> None:
    """Kiểm tra chỉ có đúng một textarea trong Apply View."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    textareas_plain = view.findChildren(QPlainTextEdit)
    textareas_rich = view.findChildren(QTextEdit)
    total_textareas = len(textareas_plain) + len(textareas_rich)
    
    assert total_textareas == 1
    assert view._opx_input is not None

def test_detection_triggers_after_800ms_debounce(qtbot) -> None:
    """Kiểm tra tính năng tự động nhận diện được kích hoạt sau 800ms debounce."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    view._opx_input.setPlainText("<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE")
    
    # Ngay lập tức kết quả detect chưa được thiết lập
    assert view._detection_result is None
    
    # Chờ 900ms để debounce kích hoạt
    qtbot.wait(900)
    
    assert view._detection_result is not None
    assert view._detection_result.has_patches is True

def test_apply_button_disabled_without_valid_patches(qtbot) -> None:
    """Nút Apply Changes bị disable khi không chứa patch hợp lệ."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    view._opx_input.setPlainText("Chào bạn, tôi muốn trò chuyện bình thường.")
    qtbot.wait(900)
    
    assert view._apply_btn is not None
    assert view._apply_btn.isEnabled() is False

def test_apply_button_enabled_with_valid_patches(qtbot) -> None:
    """Nút Apply Changes được enable khi chứa patch hợp lệ."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    view._opx_input.setPlainText("<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE")
    qtbot.wait(900)
    
    assert view._apply_btn is not None
    assert view._apply_btn.isEnabled() is True

def test_summary_label_shows_filenames(qtbot) -> None:
    """Summary label hiển thị đúng số lượng thay đổi, số file và danh sách file."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    text = (
        "<<<<<<< SEARCH src/a.py\n=======\n>>>>>>> REPLACE\n"
        "<<<<<<< SEARCH src/b.py\n=======\n>>>>>>> REPLACE"
    )
    view._opx_input.setPlainText(text)
    qtbot.wait(900)
    
    assert view._summary_label is not None
    assert view._summary_label.isVisible() is True
    summary_text = view._summary_label.text()
    assert "Tìm thấy 2 thay đổi trong 2 file" in summary_text
    assert "src/a.py" in summary_text
    assert "src/b.py" in summary_text

def test_summary_label_hidden_when_text_empty(qtbot) -> None:
    """Summary label tự động ẩn đi khi textarea trống."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    view._opx_input.setPlainText("<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE")
    qtbot.wait(900)
    assert view._summary_label.isVisible() is True
    
    view._opx_input.clear()
    qtbot.wait(900)
    assert view._summary_label.isVisible() is False

def test_paste_clipboard_button_fills_textarea(qtbot) -> None:
    """Verify việc paste clipboard chèn text vào textarea và kích hoạt detect."""
    clipboard = QApplication.clipboard()
    test_text = "<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE"
    clipboard.setText(test_text)
    
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    paste_btn = None
    for btn in view.findChildren(QPushButton):
        if btn.text() == "Paste":
            paste_btn = btn
            break
            
    assert paste_btn is not None
    qtbot.mouseClick(paste_btn, Qt.MouseButton.LeftButton)
    
    assert view._opx_input.toPlainText() == test_text

def test_textarea_clears_after_successful_apply(qtbot, monkeypatch) -> None:
    """Textarea được dọn sạch sau khi áp dụng patch thành công."""
    from infrastructure.filesystem.file_actions import ActionResult
    def mock_apply_file_actions(file_actions, roots):
        return [ActionResult(action="create", path="main.py", success=True, message="Success")]
        
    monkeypatch.setattr("presentation.views.apply.apply_view_qt.apply_file_actions", mock_apply_file_actions)
    
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    view._opx_input.setPlainText("<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE")
    qtbot.wait(900)
    
    qtbot.mouseClick(view._apply_btn, Qt.MouseButton.LeftButton)
    
    assert view._opx_input.toPlainText() == ""

def test_summary_shows_success_after_apply(qtbot, monkeypatch) -> None:
    """Nhãn tóm tắt hiển thị thông báo thành công sau khi apply."""
    from infrastructure.filesystem.file_actions import ActionResult
    def mock_apply_file_actions(file_actions, roots):
        return [ActionResult(action="create", path="main.py", success=True, message="Success")]
        
    monkeypatch.setattr("presentation.views.apply.apply_view_qt.apply_file_actions", mock_apply_file_actions)
    
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    view._opx_input.setPlainText("<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE")
    qtbot.wait(900)
    
    qtbot.mouseClick(view._apply_btn, Qt.MouseButton.LeftButton)
    
    # Chờ để đảm bảo debounce không chạy đè
    qtbot.wait(900)
    
    assert "Đã áp dụng 1 thay đổi thành công" in view._summary_label.text()
    assert view._summary_label.isVisible() is True
```

- [ ] **Step 2: Chạy pytest xác nhận các test case thực tế bị FAIL**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_apply_tab_upgrade.py -v`
Expected: FAIL (do chưa có thuộc tính `self._apply_btn`, `self._summary_label` và chưa import service)

- [ ] **Step 3: Commit**

```bash
git add tests/presentation/test_apply_tab_upgrade.py
git commit -m "test: write actual UI tests for Apply tab auto-detection"
```

---

### Task 3: Triển khai nâng cấp Apply Tab

**Files:**
- Modify: `presentation/views/apply/apply_view_qt.py`

- [ ] **Step 1: Import PatchDetectionService và QTimer**

Sửa `presentation/views/apply/apply_view_qt.py` để thêm import cần thiết:
```python
from PySide6.QtCore import Qt, Slot, QTimer
from domain.prompt.patch_detection_service import PatchDetectionService
```

- [ ] **Step 2: Khởi tạo các thuộc tính và Timer trong `__init__`**

Thêm các khai báo thuộc tính lớp vào cuối constructor `__init__`:
```python
        # State
        self.last_preview_data: Optional[PreviewData] = None
        self.last_apply_results: List[ApplyRowResult] = []
        self.last_opx_text: str = ""
        self._cached_file_actions: List = []
        self._cached_memory_block: Optional[str] = None

        self.expanded_diffs: set = set()

        # Nâng cấp Auto-detection
        self._apply_btn: Optional[QPushButton] = None
        self._summary_label: Optional[QLabel] = None
        self._detection_result = None
        
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_timeout)

        self._build_ui()
```

- [ ] **Step 3: Khởi tạo Summary Label và gán Apply Button trong `_build_left_panel`**

Sửa đổi phương thức `_build_left_panel` để khởi tạo `self._summary_label` và đặt nó vào layout.
Cụ thể, tìm khối tạo `self._opx_input` và thêm `self._summary_label`:
```python
        # Search/Replace input textarea
        self._opx_input = QPlainTextEdit()
        # ... style và layout ...
        layout.addWidget(self._opx_input, stretch=1)

        # Khởi tạo và thiết lập summary label mới
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED}; font-weight: 500; margin-top: 4px; padding-left: 2px;"
        )
        self._summary_label.hide()
        layout.addWidget(self._summary_label)

        # Lắng nghe thay đổi văn bản
        self._opx_input.textChanged.connect(self._on_text_changed)
```

Sửa khối tạo nút `apply_btn` thành gán cho `self._apply_btn` và vô hiệu hóa mặc định:
```python
        # Primary CTA: Apply Changes
        self._apply_btn = QPushButton("Apply Changes")
        self._apply_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
            QPushButton:disabled {{
                background-color: {ThemeColors.BORDER};
                color: {ThemeColors.TEXT_MUTED};
            }}
        """
        )
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.setEnabled(False)  # Mặc định disabled khi khởi tạo
        self._apply_btn.clicked.connect(self._apply_changes)
        btn_row.addWidget(self._apply_btn)
```

- [ ] **Step 4: Thêm các Slot xử lý auto-detection**

Thêm các phương thức mới vào lớp `ApplyViewQt`:
```python
    @Slot()
    def _on_text_changed(self) -> None:
        """Kích hoạt timer debounce 800ms khi văn bản thay đổi."""
        self._debounce_timer.start(800)

    @Slot()
    def _on_debounce_timeout(self) -> None:
        """Hết thời gian debounce, tiến hành phân tích patch."""
        text = self._opx_input.toPlainText()
        workspace = self.get_workspace()
        ws_root = str(workspace) if workspace else None

        detector = PatchDetectionService(workspace_root=ws_root)
        self._detection_result = detector.detect(text)
        
        self._update_detection_ui()

    def _update_detection_ui(self) -> None:
        """Cập nhật trạng thái hiển thị của Summary Label và Apply Button."""
        text = self._opx_input.toPlainText().strip()
        
        if not text:
            if self._summary_label:
                self._summary_label.hide()
            if self._apply_btn:
                self._apply_btn.setEnabled(False)
            return

        if self._detection_result and self._detection_result.has_patches:
            # Tính tổng số lượng changes
            num_changes = sum(max(1, len(a.changes)) for a in self._detection_result.file_actions)
            num_files = len(self._detection_result.affected_files)
            files_str = ", ".join(self._detection_result.affected_files)
            
            if self._summary_label:
                self._summary_label.setText(
                    f"Tìm thấy {num_changes} thay đổi trong {num_files} file: {files_str}"
                )
                self._summary_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.PRIMARY}; font-weight: 600; padding: 2px;"
                )
                self._summary_label.show()
            if self._apply_btn:
                self._apply_btn.setEnabled(True)
        else:
            if self._summary_label:
                self._summary_label.setText("Không tìm thấy patch hợp lệ")
                self._summary_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.ERROR}; font-weight: 600; padding: 2px;"
                )
                self._summary_label.show()
            if self._apply_btn:
                self._apply_btn.setEnabled(False)
```

- [ ] **Step 5: Điều chỉnh phương thức `_apply_changes` khi apply thành công**

Sửa đổi phần logic ở cuối phương thức `_apply_changes` sau khi áp dụng thành công để clear và cập nhật summary label:
```python
            # Save to history
            success_count = sum(1 for r in results if r.success)
            # ... add history entry ...

            self._show_status(
                f"Applied {success_count}/{len(results)} changes",
                is_error=success_count < len(results),
            )

            # Nếu apply thành công ít nhất một thay đổi, dọn dẹp textarea và hiện summary
            if success_count > 0:
                self._opx_input.blockSignals(True)
                self._opx_input.clear()
                self._opx_input.blockSignals(False)
                
                if self._summary_label:
                    self._summary_label.setText(f"Đã áp dụng {success_count} thay đổi thành công")
                    self._summary_label.setStyleSheet(
                        "font-size: 11px; color: #4ADE80; font-weight: 600; padding: 2px;"
                    )
                    self._summary_label.show()
                if self._apply_btn:
                    self._apply_btn.setEnabled(False)
```

- [ ] **Step 6: Sửa đổi các phương thức clear khác nếu có**

Sửa đổi `_clear_input` để ẩn `self._summary_label` và disable `self._apply_btn`:
```python
    @Slot()
    def _clear_input(self) -> None:
        self._opx_input.clear()
        self._render_empty_state()
        self._cached_file_actions.clear()
        self._cached_memory_block = None
        self._detection_result = None
        if self._summary_label:
            self._summary_label.hide()
        if self._apply_btn:
            self._apply_btn.setEnabled(False)
```

---

### Task 4: Kiểm tra và Chuẩn hóa chất lượng

- [ ] **Step 1: Chạy pytest xác nhận toàn bộ test cases PASS**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_apply_tab_upgrade.py -v`
Expected: 9 passed

- [ ] **Step 2: Đếm số lượng textarea trong file để đảm bảo không bị duplicate**

Run: `grep -n "QTextEdit\|QPlainTextEdit\|textarea\|text_edit" presentation/views/apply/apply_view_qt.py`
Expected: Chỉ tồn tại 1 lần định nghĩa `QPlainTextEdit` (không trùng lặp textarea).

- [ ] **Step 3: Chạy toàn bộ test suite của dự án**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
Expected: Tất cả tests đều pass.

- [ ] **Step 4: Chạy format & linter bằng Ruff**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format presentation/views/apply/apply_view_qt.py tests/presentation/test_apply_tab_upgrade.py
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix presentation/views/apply/apply_view_qt.py tests/presentation/test_apply_tab_upgrade.py
```
Expected: PASS không có cảnh báo nào.

- [ ] **Step 5: Chạy type check với Pyrefly**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check`
Expected: PASS không có lỗi kiểu mới.

- [ ] **Step 6: Commit**

```bash
git add presentation/views/apply/apply_view_qt.py tests/presentation/test_apply_tab_upgrade.py
git commit -m "feat: upgrade Apply tab with patch auto-detection and summary label"
```
