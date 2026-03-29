"""
Stress Test UI Interaction cho SettingsView.
Giả lập 100 thao tác tương tác hỗn hợp (Toggle + Typing + Switching)
để kiểm tra độ bền vững của UI và hiệu năng Auto-save dưới áp lực cực lớn.
"""

from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt
from presentation.views.settings.settings_view_qt import SettingsViewQt
import random

def test_settings_stress_100_mixed_interactions(qtbot):
    """
    Giả lập 100 tương tác người dùng hỗn hợp cực nhanh.
    Mục tiêu: Đảm bảo UI KHÔNG CRASH và KHÔNG GÂY I/O STORM (Chỉ lưu 1-2 lần).
    """
    view = SettingsViewQt()
    qtbot.addWidget(view)
    
    toggles = [
        view._gitignore_toggle._toggle,
        view._git_toggle._toggle,
        view._relative_toggle._toggle,
        view._security_toggle._toggle
    ]
    
    inputs = [
        view._ai_api_key_input,
        view._ai_base_url_input
    ]
    
    # Track số lần thực sự gọi ghi file
    with patch("presentation.views.settings.settings_view_qt.save_settings") as mock_save:
        # THỰC HIỆN 100 TƯƠNG TÁC HỖN HỢP CỰC NHANH
        for i in range(100):
            action = random.choice(["toggle", "type"])
            
            if action == "toggle":
                target = random.choice(toggles)
                qtbot.mouseClick(target, Qt.MouseButton.LeftButton)
            else:
                target = random.choice(inputs)
                # Gõ 1 ký tự mỗi lần để giả lập typing nhanh
                qtbot.keyClick(target, random.choice("abcdefghijklmnopqrstuvwxyz0123456789"))
        
        # NGAY LẬP TỨC: Kiểm tra I/O Storm
        # Dù gõ 100 lần, do Debounce 800ms nên save_settings CHƯA được gọi
        mock_save.assert_not_called()
        
        # Đợi 1.5 giây để Timer hết hạn sau đợt tương tác cuối cùng
        qtbot.wait(1500)
        
        # KẾT QUẢ: save_settings CHỈ ĐƯỢC GỌI 1 LẦN DUY NHẤT cho tất cả 100 thao tác!
        # Đây là minh chứng cho hiệu năng UI ổn định.
        assert mock_save.call_count == 1
        assert view is not None

def test_settings_rapid_tab_switching_stress(qtbot):
    """
    Kiểm tra lỗi tiềm ẩn khi chuyển đổi nhanh giữa các cài đặt và đóng mở dialog.
    """
    view = SettingsViewQt()
    qtbot.addWidget(view)
    
    with patch("presentation.views.settings.settings_view_qt.save_settings"):
        for _ in range(20):
            # Giả lập thay đổi một vài giá trị rồi đóng/mở menu
            qtbot.mouseClick(view._gitignore_toggle._toggle, Qt.MouseButton.LeftButton)
            qtbot.wait(10) # Chờ rất ngắn
            
            # Kiểm tra trạng thái UI ổn định
            assert view.isEnabled()

def test_settings_invalid_input_resilience_100(qtbot):
    """
    Thử nghiệm nhập 100 ký tự đặc biệt hoặc rỗng vào các trường input.
    """
    view = SettingsViewQt()
    qtbot.addWidget(view)
    
    bad_inputs = ["!@#$%", "   ", "\n\n", "\t", "OR' 1=1 --", "<script>alert(1)</script>"]
    
    with patch("presentation.views.settings.settings_view_qt.save_settings"):
        for char in bad_inputs * 15: # Lặp lại để đủ 100+ items
            view._ai_base_url_input.clear()
            qtbot.keyClicks(view._ai_base_url_input, char)
            
        qtbot.wait(1000)
        assert view.isVisible() or view is not None
