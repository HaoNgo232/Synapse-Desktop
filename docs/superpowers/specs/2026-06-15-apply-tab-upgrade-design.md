# Thiết kế Nâng cấp Apply Tab với Luồng Auto-Detection (Cập nhật Phương án B)

Tài liệu này mô tả chi tiết thiết kế kỹ thuật nâng cấp tab **Apply** (`ApplyViewQt`) trong codebase Synapse Desktop. Phiên bản này cập nhật giao diện nhãn tóm tắt hiển thị tinh gọn số lượng thay đổi và cung cấp liên kết kích hoạt Popup Menu hiển thị danh sách cuộn đầy đủ các file bị ảnh hưởng.

---

## 1. Mục tiêu (Goals)
- Tự động phát hiện patch (OPX hoặc Search/Replace) sau khi trì hoãn (debounce) 800ms.
- Hiển thị nhãn tóm tắt (Summary Label) dạng Alert Badge màu sắc dịu nhẹ và bo góc mềm mại (`border-radius: 6px`).
- **Nâng cấp UX (Phương án B)**: Nhãn tóm tắt hiển thị ngắn gọn thông tin tổng quan kèm liên kết HTML `[Show Files]`:
  * *Ví dụ*: `Found 14 changes in 14 affected files. [Show Files]`
- **Popup Menu (Show Files)**: Click vào liên kết `[Show Files]` sẽ mở ra một chiếc `QMenu` dạng danh sách cuộn (scrollable list) ngay dưới nhãn. Mỗi mục hiển thị đường dẫn của file kèm icon nhỏ.
- **Copy nhanh**: Click vào từng mục trong Popup Menu sẽ tự động copy đường dẫn của file đó vào clipboard và hiển thị thông báo toast ngắn.
- Kiểm soát nút **Apply Changes** kích hoạt/vô hiệu hóa đồng bộ.
- Đảm bảo sau khi apply thành công, textarea được làm sạch và hiển thị thông báo thành công.

---

## 2. Vị trí File & Cấu trúc Lớp
- **Giao diện sửa đổi**: `presentation/views/apply/apply_view_qt.py`
- **Unit Tests**: `tests/presentation/test_apply_tab_upgrade.py`

---

## 3. Thiết kế Chi tiết (Detailed Design)

### 3.1. Các thay đổi trong `ApplyViewQt`

#### Khởi tạo (Constructor `__init__`)
```python
# Trong ApplyViewQt.__init__
self._apply_btn: Optional[QPushButton] = None
self._summary_label: Optional[QLabel] = None
self._detection_result = None

# QTimer cho debounce 800ms
from PySide6.QtCore import QTimer
self._debounce_timer = QTimer(self)
self._debounce_timer.setSingleShot(True)
self._debounce_timer.timeout.connect(self._on_debounce_timeout)
```

#### Thiết lập Summary Label trong `_build_left_panel`
```python
self._summary_label = QLabel()
self._summary_label.setWordWrap(True)
# Cho phép QLabel tương tác với link HTML
self._summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
self._summary_label.setOpenExternalLinks(False)
self._summary_label.linkActivated.connect(self._show_affected_files_menu)

self._summary_label.setStyleSheet(
    f"font-size: 11px; color: {ThemeColors.TEXT_MUTED}; font-weight: 500; margin-top: 4px; padding-left: 2px;"
)
self._summary_label.hide()

layout.addWidget(self._opx_input, stretch=1)
layout.addWidget(self._summary_label)  # Chèn Summary Label vào layout
```

#### Slot hiển thị Popup Menu `_show_affected_files_menu`
```python
@Slot(str)
def _show_affected_files_menu(self, link_text: str) -> None:
    """Hiển thị QMenu chứa danh sách các file bị ảnh hưởng dưới dạng Popup Menu.
    
    Click vào mỗi file sẽ thực hiện copy đường dẫn của file đó vào Clipboard.
    """
    if not self._detection_result or not self._detection_result.affected_files:
        return

    from PySide6.QtWidgets import QMenu
    menu = QMenu(self)
    menu.setStyleSheet(
        f"QMenu {{"
        f"  background-color: {ThemeColors.BG_ELEVATED};"
        f"  border: 1px solid {ThemeColors.BORDER};"
        f"  border-radius: 6px;"
        f"  padding: 4px 0px;"
        f"}}"
        f"QMenu::item {{"
        f"  padding: 6px 16px;"
        f"  color: {ThemeColors.TEXT_PRIMARY};"
        f"  font-family: 'Cascadia Code', 'Fira Code', monospace;"
        f"  font-size: 11px;"
        f"}}"
        f"QMenu::item:selected {{"
        f"  background-color: {ThemeColors.PRIMARY};"
        f"  color: white;"
        f"}}"
    )

    for file_path in self._detection_result.affected_files:
        action = menu.addAction(f"📄  {file_path}")
        action.setToolTip("Click to copy file path")
        # Kết nối sự kiện để copy path khi được click
        action.triggered.connect(
            lambda checked=False, p=file_path: (
                copy_to_clipboard(p),
                self._show_status(f"Copied: {p}")
            )
        )

    # Hiển thị menu ngay bên dưới nhãn tóm tắt
    pos = self._summary_label.mapToGlobal(self._summary_label.rect().bottomLeft())
    pos.setY(pos.y() + 4)
    menu.exec(pos)
```

#### Phương thức cập nhật UI `_update_detection_ui`
```python
def _update_detection_ui(self) -> None:
    """Cập nhật trạng thái hiển thị của Summary Label và Apply Button."""
    text = self._opx_input.toPlainText().strip()
    
    if not text:
        self._summary_label.hide()
        if self._apply_btn:
            self._apply_btn.setEnabled(False)
        return

    if self._detection_result and self._detection_result.has_patches:
        num_changes = sum(max(1, len(a.changes)) for a in self._detection_result.file_actions)
        num_files = len(self._detection_result.affected_files)
        
        # Thiết lập text chứa HTML link
        self._summary_label.setText(
            f"Found {num_changes} changes in {num_files} affected files. "
            f"<a href='show_files' style='color: {ThemeColors.PRIMARY}; text-decoration: none; font-weight: bold;'>[Show Files]</a>"
        )
        self._summary_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.PRIMARY}; font-weight: 600; "
            f"background-color: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.2); "
            f"border-radius: 6px; padding: 6px 10px; margin-top: 4px;"
        )
        self._summary_label.show()
        if self._apply_btn:
            self._apply_btn.setEnabled(True)
    else:
        self._summary_label.setText("No valid patch found")
        self._summary_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.ERROR}; font-weight: 600; "
            f"background-color: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); "
            f"border-radius: 6px; padding: 6px 10px; margin-top: 4px;"
        )
        self._summary_label.show()
        if self._apply_btn:
            self._apply_btn.setEnabled(False)
```

---

## 4. Kế hoạch Kiểm thử (Verification Plan)

### Cập nhật Unit Tests (`test_apply_tab_upgrade.py`)
Chúng ta sẽ điều chỉnh test case `test_summary_label_shows_filenames` để tương thích với HTML link mới:
```python
def test_summary_label_shows_filenames(qtbot) -> None:
    """Summary label hiển thị đúng liên kết Show Files."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)
    
    text = (
        "<<<<<<< SEARCH src/a.py\n=======\n>>>>>>> REPLACE\n"
        "<<<<<<< SEARCH src/b.py\n=======\n>>>>>>> REPLACE"
    )
    view._opx_input.setPlainText(text)
    qtbot.wait(900)
    
    assert view._summary_label is not None
    assert not view._summary_label.isHidden()
    summary_text = view._summary_label.text()
    assert "Found 2 changes in 2 affected files" in summary_text
    assert "[Show Files]" in summary_text
```
