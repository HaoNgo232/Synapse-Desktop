import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QPlainTextEdit,
    QTextEdit,
    QPushButton,
    QApplication,
)
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


def test_summary_label_shows_show_files_link(qtbot) -> None:
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


def test_summary_label_hidden_when_text_empty(qtbot) -> None:
    """Summary label tự động ẩn đi khi textarea trống."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    view._opx_input.setPlainText("<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE")
    qtbot.wait(900)
    assert not view._summary_label.isHidden()

    view._opx_input.clear()
    qtbot.wait(900)
    assert view._summary_label.isHidden()


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
        return [
            ActionResult(
                action="create", path="main.py", success=True, message="Success"
            )
        ]

    monkeypatch.setattr(
        "presentation.views.apply.apply_view_qt.apply_file_actions",
        mock_apply_file_actions,
    )

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

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
        return [
            ActionResult(
                action="create", path="main.py", success=True, message="Success"
            )
        ]

    monkeypatch.setattr(
        "presentation.views.apply.apply_view_qt.apply_file_actions",
        mock_apply_file_actions,
    )

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    view._opx_input.setPlainText("<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE")
    qtbot.wait(900)

    qtbot.mouseClick(view._apply_btn, Qt.MouseButton.LeftButton)

    # Chờ để đảm bảo debounce không chạy đè
    qtbot.wait(900)

    assert "Successfully applied 1 changes" in view._summary_label.text()
    assert not view._summary_label.isHidden()
