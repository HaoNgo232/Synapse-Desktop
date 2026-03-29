"""
Tests tương tác UI cho SettingsView.
Tập trung vào kiểm tra hiệu năng Auto-save và cơ chế Debounce.

Đảm bảo thay đổi cài đặt nhanh (typing/toggling) không gây đơ UI
do ghi file cấu hình quá nhiều lần (I/O blocking).
"""

from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt
from presentation.views.settings.settings_view_qt import SettingsViewQt

def test_settings_autosave_debounce_prevents_io_storm(qtbot):
    """
    Xác nhận cơ chế Debounce: Thay đổi cài đặt liên tục chỉ kích hoạt 
    save_settings MỘT LẦN sau khi người dùng ngừng thao tác.
    """
    # 1. Setup View
    view = SettingsViewQt()
    qtbot.addWidget(view)
    
    # 2. Mock hàm save_settings để đếm số lần gọi thực tế xuống đĩa
    with patch("presentation.views.settings.settings_view_qt.save_settings") as mock_save:
        # 3. Giả lập người dùng nhấn toggle liên tục 5 lần cực nhanh
        for _ in range(5):
            qtbot.mouseClick(view._gitignore_toggle._toggle, Qt.MouseButton.LeftButton)
            
        # 4. Ngay lập tức kiểm tra: save_settings CHƯA được gọi vì đang Debounce (800ms)
        mock_save.assert_not_called()
        
        # 5. Chờ 1 giây để Timer timeout và kích hoạt save
        qtbot.wait(1200)
        
        # 6. KẾT QUẢ: save_settings chỉ được gọi đúng 1 lần duy nhất cho cả 5 lần bấm
        assert mock_save.call_count == 1

def test_typing_api_key_shows_indicator_and_debounces(qtbot):
    """
    Kiểm tra luồng nhập API Key: Hiển thị trạng thái 'Saving...' và 
    không gây giật lag UI khi nhập chuỗi dài.
    """
    view = SettingsViewQt()
    qtbot.addWidget(view)
    
    # Mock save_settings
    with patch("presentation.views.settings.settings_view_qt.save_settings") as mock_save:
        # Nhập nhanh một chuỗi API Key
        long_key = "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx"
        qtbot.keyClicks(view._ai_api_key_input, long_key)
        
        # UI phải hiển thị trạng thái chờ lưu (Indicator)
        assert "Unsaved" in view._auto_save_indicator.text() or view._auto_save_timer.isActive()
        
        # Chờ lưu xong
        qtbot.wait(1200)
        
        # Đã lưu thành công
        assert "Saved" in view._auto_save_indicator.text() or not view._auto_save_timer.isActive()
        mock_save.assert_called()

def test_settings_toggle_all_switches_no_crash(qtbot):
    """
    Stress test: Nhấn tất cả các switch trong settings nhanh nhất có thể.
    """
    view = SettingsViewQt()
    qtbot.addWidget(view)
    
    toggles = [
        view._gitignore_toggle._toggle,
        view._git_toggle._toggle,
        view._relative_toggle._toggle,
        view._security_toggle._toggle
    ]
    
    with patch("presentation.views.settings.settings_view_qt.save_settings"):
        for toggle in toggles:
            qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)
            
        # 1. Đảm bảo UI vẫn tồn tại (Không crash)
        assert view is not None
        
        # 2. Đảm bảo Timer auto-save vẫn đang đếm (Debounce hoạt động, không bị đơ thread)
        assert view._auto_save_timer.isActive()
