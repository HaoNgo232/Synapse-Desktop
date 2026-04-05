from unittest.mock import patch
from pathlib import Path

# Mock fonts and theme before importing MainWindow
with patch("presentation.config.theme.ThemeFonts.load_fonts"):
    from presentation.main_window import SynapseMainWindow


def test_main_window_initialization(qtbot):
    """Kiểm tra MainWindow khởi tạo thành công và chứa các tabs cơ bản."""
    with (
        patch("presentation.main_window.get_memory_monitor"),
        patch("presentation.components.toast.toast_qt.init_toast_manager"),
        patch(
            "presentation.main_window.load_session_state",
            return_value=None,
        ),
        patch(
            "presentation.main_window.load_recent_folders",
            return_value=[],
        ),
    ):
        window = SynapseMainWindow()
        qtbot.addWidget(window)

        # Kiểm tra title ban đầu
        assert "No project open" in window.windowTitle()

        # Kiểm tra số lượng tab
        assert window.tab_widget.count() == 4

        # Thử chuyển tab sang Settings (index 3)
        window.tab_widget.setCurrentIndex(3)
        assert window._current_tab_index == 3


def test_main_window_open_folder(qtbot, tmp_path):
    """Kiểm tra chức năng mô phỏng mở folder qua QFileDialog."""
    with (
        patch("presentation.main_window.get_memory_monitor"),
        patch("presentation.components.toast.toast_qt.init_toast_manager"),
        patch(
            "presentation.main_window.load_session_state",
            return_value=None,
        ),
        patch(
            "presentation.main_window.load_recent_folders",
            return_value=[],
        ),
    ):
        window = SynapseMainWindow()
        qtbot.addWidget(window)

        fake_dir = str(tmp_path)
        with patch(
            "presentation.main_window.QFileDialog.getExistingDirectory",
            return_value=fake_dir,
        ):
            # Gọi hàm mở folder (bật từ nút Open Folder)
            window._open_folder_dialog()

            # Kiểm tra xem project path đã được set chưa
            assert window.workspace_path == Path(fake_dir)

            # Kiểm tra text label của status bar và breadcrumb
            assert fake_dir in window.status_bar._status_workspace.text()
            assert fake_dir in window.top_bar._folder_path_label.text()
