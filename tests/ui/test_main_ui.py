from unittest.mock import patch
from pathlib import Path

# Mock fonts and theme before importing MainWindow
with patch("core.theme.ThemeFonts.load_fonts"):
    from main_window import SynapseMainWindow


def test_main_window_initialization(qtbot):
    """Kiểm tra MainWindow khởi tạo thành công và chứa các tabs cơ bản."""
    with (
        patch("main_window.get_memory_monitor"),
        patch("components.toast_qt.init_toast_manager"),
        patch("services.session_state.load_session_state", return_value=None),
        patch("services.recent_folders.load_recent_folders", return_value=[]),
    ):
        window = SynapseMainWindow()
        qtbot.addWidget(window)

        # Kiểm tra title ban đầu
        assert "No project open" in window.windowTitle()

        # Kiểm tra số lượng tab
        assert window.tab_widget.count() == 5

        # Thử chuyển tab sang Settings (index 4)
        window.tab_widget.setCurrentIndex(4)
        assert window._current_tab_index == 4


def test_main_window_open_folder(qtbot, tmp_path):
    """Kiểm tra chức năng mô phỏng mở folder qua QFileDialog."""
    with (
        patch("main_window.get_memory_monitor"),
        patch("components.toast_qt.init_toast_manager"),
        patch("services.session_state.load_session_state", return_value=None),
        patch("services.recent_folders.load_recent_folders", return_value=[]),
    ):
        window = SynapseMainWindow()
        qtbot.addWidget(window)

        fake_dir = str(tmp_path)
        with patch(
            "main_window.QFileDialog.getExistingDirectory", return_value=fake_dir
        ):
            # Gọi hàm mở folder (bật từ nút Open Folder)
            window._open_folder_dialog()

            # Kiểm tra xem project path đã được set chưa
            assert window.workspace_path == Path(fake_dir)

            # Kiểm tra text label của status bar và breadcrumb
            assert fake_dir in window._status_workspace.text()
            assert fake_dir in window._folder_path_label.text()
