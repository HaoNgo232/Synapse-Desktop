"""
Tests cho copy mode selector mới trong ContextViewQt.
"""
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QButtonGroup
from domain.prompt.copy_mode import CopyMode, CopyConfig
from tests.ui.conftest import FakeFileTreeWidget, FakeTokenStatsPanel

def test_only_3_mode_buttons_present(qtbot, context_view):
    """Xác nhận chỉ có 3 nút chọn mode (Full, Smart, Apply) dạng QButtonGroup exclusive trên UI."""
    view = context_view
    view.show()
    
    # Mode buttons phải tồn tại
    assert hasattr(view, "_mode_full_btn")
    assert hasattr(view, "_mode_smart_btn")
    assert hasattr(view, "_mode_apply_btn")
    assert hasattr(view, "_mode_group")
    
    assert isinstance(view._mode_full_btn, QPushButton)
    assert isinstance(view._mode_smart_btn, QPushButton)
    assert isinstance(view._mode_apply_btn, QPushButton)
    assert isinstance(view._mode_group, QButtonGroup)
    
    # 3 button phải checkable và thuộc button group
    assert view._mode_full_btn.isCheckable()
    assert view._mode_smart_btn.isCheckable()
    assert view._mode_apply_btn.isCheckable()
    
    assert view._mode_group.exclusive()
    assert view._mode_group.button(0) == view._mode_full_btn
    assert view._mode_group.button(1) == view._mode_smart_btn
    assert view._mode_group.button(2) == view._mode_apply_btn

def test_modes_mutually_exclusive(qtbot, context_view):
    """Xác nhận việc chọn mode là mutually exclusive (chỉ 1 mode được checked)."""
    view = context_view
    view.show()
    
    # Click Smart
    qtbot.mouseClick(view._mode_smart_btn, Qt.MouseButton.LeftButton)
    assert view._mode_smart_btn.isChecked()
    assert not view._mode_full_btn.isChecked()
    assert not view._mode_apply_btn.isChecked()
    
    # Click Apply
    qtbot.mouseClick(view._mode_apply_btn, Qt.MouseButton.LeftButton)
    assert view._mode_apply_btn.isChecked()
    assert not view._mode_full_btn.isChecked()
    assert not view._mode_smart_btn.isChecked()

def test_tree_map_only_disables_mode_buttons(qtbot, context_view):
    """Tích chọn 'Tree Map only' sẽ disable 3 mode buttons và khôi phục khi bỏ tích."""
    view = context_view
    view.show()
    
    # Check tree map only
    view._tree_map_only_cb.setChecked(True)
    assert not view._mode_full_btn.isEnabled()
    assert not view._mode_smart_btn.isEnabled()
    assert not view._mode_apply_btn.isEnabled()
    
    # Uncheck tree map only
    view._tree_map_only_cb.setChecked(False)
    assert view._mode_full_btn.isEnabled()
    assert view._mode_smart_btn.isEnabled()
    assert view._mode_apply_btn.isEnabled()

def test_git_diff_checkbox_independent(qtbot, context_view):
    """Checkbox 'Include Git Diff' hoạt động độc lập, không làm thay đổi hay disable mode buttons."""
    view = context_view
    view.show()
    
    # Chọn Full mode
    view._mode_full_btn.setChecked(True)
    
    # Toggle Git Diff Checkbox
    view._git_diff_cb.setChecked(True)
    assert view._mode_full_btn.isChecked()
    assert view._mode_full_btn.isEnabled()
    
    view._git_diff_cb.setChecked(False)
    assert view._mode_full_btn.isChecked()
    assert view._mode_full_btn.isEnabled()

def test_mode_persists_after_restart(qtbot, monkeypatch):
    """Xác nhận state của selector (mode, checkboxes) được persist qua session settings."""
    from presentation.views.context.context_view_qt import ContextViewQt
    from pathlib import Path
    
    mock_settings = MagicMock()
    mock_settings.output_format = "xml"
    mock_settings.include_git_changes = True
    # Giả lập settings lưu trữ copy_mode
    mock_settings.copy_mode = "smart"
    mock_settings.tree_map_only = True
    
    # Mock settings manager
    monkeypatch.setattr(
        "presentation.views.context.ui_builder.load_app_settings",
        lambda: mock_settings
    )
    monkeypatch.setattr(
        "infrastructure.persistence.settings_manager.load_app_settings",
        lambda: mock_settings
    )
    
    # Khởi tạo view mới
    mock_pb = MagicMock()
    mock_pb.count_tokens.return_value = 0
    
    with patch("presentation.views.context.ui_builder.FileTreeWidget", FakeFileTreeWidget), \
         patch("presentation.views.context.ui_builder.TokenStatsPanelQt", FakeTokenStatsPanel), \
         patch("presentation.views.context.context_view_qt.FileWatcher"):
        
        view = ContextViewQt(
            get_workspace=lambda: Path("/fake"),
            prompt_builder=mock_pb,
            clipboard_service=MagicMock()
        )
        qtbot.addWidget(view)
        view.show()
        
        # Verify settings được restore chính xác lên UI
        assert view._mode_smart_btn.isChecked()
        assert view._git_diff_cb.isChecked()
        assert view._tree_map_only_cb.isChecked()

def test_copy_logic_receives_copy_config_object(qtbot, context_view):
    """Khi thực hiện copy, logic copy nhận được đúng CopyConfig object phản ánh state của UI."""
    view = context_view
    view.show()
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=["/project/a.py"])
    
    # Đặt UI state: Smart mode, Include Git Diff = True, Tree Map only = False
    view._mode_smart_btn.setChecked(True)
    view._git_diff_cb.setChecked(True)
    view._tree_map_only_cb.setChecked(False)
    
    # Click Copy button chính (view._copy_btn)
    with patch.object(view._copy_controller, "_run_copy_in_background") as mock_run:
        # Nhấn nút copy chính
        qtbot.mouseClick(view._copy_btn, Qt.MouseButton.LeftButton)
        
        # Kiểm tra task function được tạo ra trong controller có truyền config đúng hay không
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        task_fn = args[1]
        
        # Mock scan_full_tree để tránh chạy Git/FileSystem thật
        view.scan_full_tree = MagicMock()
        
        # Mock build_prompt để xem config truyền vào là gì
        with patch.object(view._prompt_builder, "build_prompt") as mock_build:
            # Gọi thử task_fn chạy trên background thread
            try:
                task_fn()
            except Exception:
                pass
            
            # verify build_prompt nhận config phù hợp
            mock_build.assert_called_once()
            _, build_kwargs = mock_build.call_args
            config = build_kwargs.get("output_format")
            assert isinstance(config, CopyConfig)
            assert config.mode == CopyMode.SMART
            assert config.include_git_diff is True
            assert config.tree_map_only is False

def test_no_legacy_mode_ui_remaining(qtbot, context_view):
    """Xác nhận không còn widget hiển thị nào cho các mode cũ."""
    view = context_view
    view.show()
    
    # Các nút cũ phải được ẩn khỏi giao diện (không visible)
    # Lưu ý: Các thuộc tính vẫn phải tồn tại (aliases) nhưng widget thực tế phải ẩn
    assert not view._smart_btn.isVisible()
    assert not view._opx_btn.isVisible()
    assert not view._diff_btn.isVisible()
    assert not view._tree_map_btn.isVisible()

def test_git_commit_depth_selector_present(qtbot, context_view):
    """Xác nhận sự tồn tại của bộ chọn commit depth (QSpinBox) và nút cấu hình nâng cao trên UI."""
    view = context_view
    view.show()
    
    assert hasattr(view, "_commit_depth_spin")
    assert hasattr(view, "_mode_diff_config_btn")
    
    from PySide6.QtWidgets import QSpinBox, QToolButton
    assert isinstance(view._commit_depth_spin, QSpinBox)
    assert isinstance(view._mode_diff_config_btn, QToolButton)

def test_git_commit_depth_persists(qtbot, monkeypatch):
    """Đảm bảo cấu hình commit depth được lưu và khôi phục từ settings."""
    from presentation.views.context.context_view_qt import ContextViewQt
    from pathlib import Path
    
    mock_settings = MagicMock()
    mock_settings.output_format = "xml"
    mock_settings.include_git_changes = True
    mock_settings.copy_mode = "full"
    mock_settings.tree_map_only = False
    mock_settings.git_commit_depth = 8  # Giả lập load giá trị 8
    
    # Mock settings manager
    monkeypatch.setattr(
        "presentation.views.context.ui_builder.load_app_settings",
        lambda: mock_settings
    )
    monkeypatch.setattr(
        "infrastructure.persistence.settings_manager.load_app_settings",
        lambda: mock_settings
    )
    
    mock_pb = MagicMock()
    mock_pb.count_tokens.return_value = 0
    
    with patch("presentation.views.context.ui_builder.FileTreeWidget", FakeFileTreeWidget), \
         patch("presentation.views.context.ui_builder.TokenStatsPanelQt", FakeTokenStatsPanel), \
         patch("presentation.views.context.context_view_qt.FileWatcher"):
        
        view = ContextViewQt(
            get_workspace=lambda: Path("/fake"),
            prompt_builder=mock_pb,
            clipboard_service=MagicMock()
        )
        qtbot.addWidget(view)
        view.show()
        
        assert view._commit_depth_spin.value() == 8

def test_copy_logic_receives_git_commit_depth(qtbot, context_view):
    """Đảm bảo CopyConfig được tạo và truyền đi chứa đúng giá trị git_commit_depth cấu hình trên UI."""
    view = context_view
    view.show()
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=["/project/a.py"])
    
    # Đặt UI state: Full mode, Include Git Diff = True, commit depth = 12
    view._mode_full_btn.setChecked(True)
    view._git_diff_cb.setChecked(True)
    view._commit_depth_spin.setValue(12)
    
    # Tắt security check để gọi trực tiếp _run_copy_in_background đồng bộ trong test
    with patch("presentation.views.context.copy_action_controller.load_app_settings") as mock_load:
        mock_settings = MagicMock()
        mock_settings.enable_security_check = False
        mock_settings.include_git_changes = True
        mock_settings.git_commit_depth = 12
        mock_settings.copy_mode = "full"
        mock_settings.tree_map_only = False
        mock_load.return_value = mock_settings
        
        with patch.object(view._copy_controller, "_run_copy_in_background") as mock_run:
            qtbot.mouseClick(view._copy_btn, Qt.MouseButton.LeftButton)
            
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            task_fn = args[1]
            
            view.scan_full_tree = MagicMock()
            
            with patch.object(view._prompt_builder, "build_prompt") as mock_build:
                print("VIEW_PB_TYPE:", type(view._prompt_builder))
                print("VIEW_PB_ID:", id(view._prompt_builder))
                print("VIEW_GET_PB_ID:", id(view.get_prompt_builder()))
                res = task_fn()
                print("DEBUG_RES:", res)
                
                mock_build.assert_called_once()
                _, build_kwargs = mock_build.call_args
                config = build_kwargs.get("output_format")
                assert isinstance(config, CopyConfig)
                assert config.include_git_diff is True
                assert config.git_commit_depth == 12

def test_advanced_configure_opens_dialog(qtbot, context_view):
    """Xác nhận việc click nút cấu hình nâng cao sẽ mở DiffOnlyDialogQt."""
    view = context_view
    view.show()
    
    # Mock workspace path
    from pathlib import Path
    view.get_workspace = MagicMock(return_value=Path("/fake"))
    
    with patch("presentation.components.dialogs.dialogs_qt.DiffOnlyDialogQt") as mock_dialog:
        mock_dialog.return_value.exec = MagicMock(return_value=1)
        
        # Click nút ⚙️
        qtbot.mouseClick(view._mode_diff_config_btn, Qt.MouseButton.LeftButton)
        
        # Đảm bảo dialog được khởi tạo và chạy
        mock_dialog.assert_called_once()

def test_copy_allowed_with_no_files_selected_if_git_diff_checked(qtbot, context_view):
    """Xác nhận hành động copy vẫn được phép khi không có file nào được chọn nếu tích chọn Include Git Diff."""
    view = context_view
    view.show()
    view.file_tree_widget.get_selected_paths = MagicMock(return_value=[])

    # Thiết lập UI: Không chọn file, tích chọn Git Diff
    view._mode_full_btn.setChecked(True)
    view._git_diff_cb.setChecked(True)

    with patch("presentation.views.context.copy_action_controller.load_app_settings") as mock_load:
        mock_settings = MagicMock()
        mock_settings.enable_security_check = False
        mock_settings.include_git_changes = True
        mock_settings.copy_mode = "full"
        mock_settings.tree_map_only = False
        mock_load.return_value = mock_settings

        with patch.object(view._copy_controller, "_run_copy_in_background") as mock_run:
            qtbot.mouseClick(view._copy_btn, Qt.MouseButton.LeftButton)

            # Đảm bảo task copy trong background được kích hoạt mặc dù danh sách files trống
            mock_run.assert_called_once()

def test_mode_buttons_have_correct_tooltips(qtbot, context_view):
    """Xác nhận các nút Full, Smart, Apply có đúng tooltip mô tả tương ứng."""
    view = context_view
    view.show()

    from domain.prompt.copy_mode import CopyMode
    assert view._mode_full_btn.toolTip() == CopyMode.FULL.description
    assert view._mode_smart_btn.toolTip() == CopyMode.SMART.description
    assert view._mode_apply_btn.toolTip() == CopyMode.APPLY.description
