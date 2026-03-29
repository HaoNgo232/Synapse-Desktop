"""
Tests tương tác UI cho cụm tính năng Copy Actions.
Sử dụng qtbot để giả lập click chuột thật trên các button.

Đảm bảo các thay đổi core logic sau refactor không làm mất kết nối UI.
"""

from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt
import pytest

def test_copy_button_click_triggers_logic(qtbot, context_view):
    """
    Xác nhận việc nhấn nút 'Copy' thật sự kích hoạt logic copy_context.
    """
    view = context_view
    # Giả lập có file được chọn
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=["/project/a.py"])
    
    # Mock controller logic để kiểm tra kết nối
    with patch.object(view._copy_controller, "_copy_context") as mock_copy:
        # THỰC HIỆN CLICK CHUỘT THẬT
        qtbot.mouseClick(view._copy_btn, Qt.MouseButton.LeftButton)
        
        # Kiểm tra kết nối Signal/Slot
        mock_copy.assert_called_once()

def test_copy_plus_opx_click_triggers_logic(qtbot, context_view):
    """
    Xác nhận việc nhấn nút 'Copy + OPX' kích hoạt đúng logic tương ứng.
    """
    view = context_view
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=["/project/a.py"])
    
    with patch.object(view._copy_controller, "on_copy_context_requested") as mock_copy:
        # Nút nhấn thực tế lầ _opx_btn
        qtbot.mouseClick(view._opx_btn, Qt.MouseButton.LeftButton)
        
        # Nút OPX gọi on_copy_context_requested(include_xml=True)
        mock_copy.assert_called_once_with(include_xml=True)

def test_compress_button_click_triggers_logic(qtbot, context_view):
    """
    Xác nhận việc nhấn nút 'Compress' kích hoạt đúng logic tương ứng.
    """
    view = context_view
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=["/project/a.py"])
    
    with patch.object(view._copy_controller, "on_copy_smart_requested") as mock_compress:
        # Nút nhấn thực tế là _smart_btn
        qtbot.mouseClick(view._smart_btn, Qt.MouseButton.LeftButton)
        
        mock_compress.assert_called_once()

def test_copy_diff_button_click_triggers_logic(qtbot, context_view):
    """
    Xác nhận việc nhấn nút 'Git Diff' (biểu tượng Git) kích hoạt đúng logic tương ứng.
    """
    view = context_view
    # Nút nhấn thực tế là _diff_btn
    with patch.object(view._copy_controller, "_show_diff_only_dialog") as mock_diff:
        qtbot.mouseClick(view._diff_btn, Qt.MouseButton.LeftButton)
        mock_diff.assert_called_once()

def test_copy_button_disables_during_operation(qtbot, context_view):
    """
    Kiểm tra xem nút Copy có bị disable khi đang thực hiện tác vụ (Thread safety).
    """
    view = context_view
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=["/project/a.py"])
    
    # Giả lập một tác vụ chạy nền (Background thread)
    view._copy_controller._begin_copy_operation()
    
    # Các nút bấm phải mờ đi (Disabled) để tránh Double Click
    assert not view._copy_btn.isEnabled()
    assert not view._smart_btn.isEnabled()
    assert not view._opx_btn.isEnabled()
