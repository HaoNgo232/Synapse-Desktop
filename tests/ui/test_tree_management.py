"""Tests cho TreeManagementMixin - refresh, ignore, watcher callbacks.

Su dung context_view fixture tu conftest.py.
Covers: lines 29-135 cua _tree_management.py
"""

from unittest.mock import patch, MagicMock
from pathlib import Path


def test_refresh_tree(context_view):
    """Kiem tra _refresh_tree goi file_tree_widget.load_tree."""
    view = context_view
    view.file_tree_widget.load_tree = MagicMock()
    view._refresh_tree()
    view.file_tree_widget.load_tree.assert_called_once_with(Path("/fake/workspace"))


def test_refresh_tree_no_workspace(qtbot):
    """Kiem tra _refresh_tree khong lam gi khi khong co workspace."""
    from tests.ui.conftest import FakeFileTreeWidget, FakeTokenStatsPanel

    mock_app_settings = MagicMock()
    mock_app_settings.output_format = None

    with (
        patch("views.context._ui_builder.FileTreeWidget", FakeFileTreeWidget),
        patch("views.context._ui_builder.TokenStatsPanelQt", FakeTokenStatsPanel),
        patch(
            "views.context._ui_builder.load_app_settings",
            return_value=mock_app_settings,
        ),
        patch("core.prompting.template_manager.list_templates", return_value=[]),
        patch("views.context_view_qt.FileWatcher", return_value=MagicMock()),
    ):
        from views.context_view_qt import ContextViewQt

        view = ContextViewQt(
            get_workspace=lambda: None,
            prompt_builder=MagicMock(),
            clipboard_service=MagicMock(),
        )
        qtbot.addWidget(view)
        view.file_tree_widget.load_tree = MagicMock()
        view._refresh_tree()
        view.file_tree_widget.load_tree.assert_not_called()


@patch("services.workspace_config.add_excluded_patterns", return_value=True)
def test_add_to_ignore(mock_add, context_view):
    """Kiem tra _add_to_ignore them patterns va refresh tree."""
    view = context_view
    view.file_tree_widget.get_all_selected_paths = MagicMock(
        return_value={"/fake/workspace/src/main.py"}
    )
    view.file_tree_widget.load_tree = MagicMock()

    view._add_to_ignore()

    mock_add.assert_called_once()
    assert len(view._last_ignored_patterns) > 0


def test_add_to_ignore_no_selection(context_view):
    """Kiem tra _add_to_ignore khi khong co file duoc chon."""
    view = context_view
    view.file_tree_widget.get_all_selected_paths = MagicMock(return_value=set())
    view._add_to_ignore()


def test_add_to_ignore_no_workspace(context_view):
    """Kiem tra _add_to_ignore khi khong co workspace (line 44-45)."""
    view = context_view
    view.get_workspace = lambda: None
    view.file_tree_widget.get_all_selected_paths = MagicMock(
        return_value={"/some/file.py"}
    )
    view._add_to_ignore()


def test_add_to_ignore_value_error_in_relative(context_view):
    """Kiem tra _add_to_ignore khi ValueError khi relative_to (line 55-56)."""
    view = context_view
    view.file_tree_widget.get_all_selected_paths = MagicMock(
        return_value={"/completely/different/path/file.py"}
    )
    view.file_tree_widget.load_tree = MagicMock()
    with patch("services.workspace_config.add_excluded_patterns", return_value=True):
        view._add_to_ignore()


@patch("services.workspace_config.remove_excluded_patterns", return_value=True)
def test_undo_ignore(mock_remove, context_view):
    """Kiem tra _undo_ignore xoa patterns da them."""
    view = context_view
    view._last_ignored_patterns = ["src/main.py", "src/utils.py"]
    view.file_tree_widget.load_tree = MagicMock()

    view._undo_ignore()

    mock_remove.assert_called_once_with(["src/main.py", "src/utils.py"])
    assert view._last_ignored_patterns == []


def test_undo_ignore_nothing_to_undo(context_view):
    """Kiem tra _undo_ignore khi khong co gi de undo."""
    view = context_view
    view._last_ignored_patterns = []
    view._undo_ignore()


@patch("components.dialogs_qt.FilePreviewDialogQt")
def test_preview_file(mock_dialog, context_view):
    """Kiem tra _preview_file goi FilePreviewDialogQt.show_preview (line 80-82)."""
    view = context_view
    view._preview_file("/fake/workspace/src/main.py")
    mock_dialog.show_preview.assert_called_once_with(
        view, "/fake/workspace/src/main.py"
    )


@patch("components.dialogs_qt.RemoteRepoDialogQt")
@patch("core.utils.repo_manager.RepoManager")
def test_open_remote_repo_dialog(mock_repo_mgr, mock_dialog, context_view):
    """Kiem tra _open_remote_repo_dialog tao dialog va exec (line 84-98)."""
    view = context_view
    view._repo_manager = None
    mock_dialog_instance = MagicMock()
    mock_dialog.return_value = mock_dialog_instance

    view._open_remote_repo_dialog()

    assert view._repo_manager is not None
    mock_dialog.assert_called_once()
    mock_dialog_instance.exec.assert_called_once()


@patch("components.dialogs_qt.RemoteRepoDialogQt")
def test_open_remote_repo_dialog_existing_manager(mock_dialog, context_view):
    """Kiem tra _open_remote_repo_dialog reuse existing repo manager."""
    view = context_view
    existing_manager = MagicMock()
    view._repo_manager = existing_manager
    mock_dialog_instance = MagicMock()
    mock_dialog.return_value = mock_dialog_instance

    view._open_remote_repo_dialog()

    assert view._repo_manager is existing_manager


@patch("components.dialogs_qt.CacheManagementDialogQt")
@patch("core.utils.repo_manager.RepoManager")
def test_open_cache_management_dialog(mock_repo_mgr, mock_dialog, context_view):
    """Kiem tra _open_cache_management_dialog tao dialog va exec (line 100-113)."""
    view = context_view
    view._repo_manager = None
    mock_dialog_instance = MagicMock()
    mock_dialog.return_value = mock_dialog_instance

    view._open_cache_management_dialog()

    assert view._repo_manager is not None
    mock_dialog.assert_called_once()
    mock_dialog_instance.exec.assert_called_once()


@patch("services.cache_registry.cache_registry")
def test_on_file_modified(mock_registry, context_view):
    """Kiem tra _on_file_modified invalidate caches."""
    view = context_view
    view._on_file_modified("/fake/workspace/src/main.py")
    mock_registry.invalidate_for_path.assert_called_once_with(
        "/fake/workspace/src/main.py"
    )


def test_on_file_deleted_delegates(context_view):
    """Kiem tra _on_file_deleted goi _on_file_modified."""
    view = context_view
    view._on_file_modified = MagicMock()
    view._on_file_deleted("/fake/workspace/old.py")
    view._on_file_modified.assert_called_once_with("/fake/workspace/old.py")


def test_on_file_created_no_crash(context_view):
    """Kiem tra _on_file_created khong lam gi (no cache invalidation)."""
    view = context_view
    view._on_file_created("/fake/workspace/new.py")


@patch("views.context._tree_management.run_on_main_thread")
def test_on_file_system_changed(mock_run, context_view):
    """Kiem tra _on_file_system_changed dispatch refresh len main thread."""
    view = context_view
    view._on_file_system_changed()
    mock_run.assert_called_once()


@patch("views.context._tree_management.run_on_main_thread")
def test_on_file_system_changed_no_workspace(mock_run, qtbot):
    """Kiem tra _on_file_system_changed khong lam gi khi khong co workspace."""
    from tests.ui.conftest import FakeFileTreeWidget, FakeTokenStatsPanel

    mock_app_settings = MagicMock()
    mock_app_settings.output_format = None

    with (
        patch("views.context._ui_builder.FileTreeWidget", FakeFileTreeWidget),
        patch("views.context._ui_builder.TokenStatsPanelQt", FakeTokenStatsPanel),
        patch(
            "views.context._ui_builder.load_app_settings",
            return_value=mock_app_settings,
        ),
        patch("core.prompting.template_manager.list_templates", return_value=[]),
        patch("views.context_view_qt.FileWatcher", return_value=MagicMock()),
    ):
        from views.context_view_qt import ContextViewQt

        view = ContextViewQt(
            get_workspace=lambda: None,
            prompt_builder=MagicMock(),
            clipboard_service=MagicMock(),
        )
        qtbot.addWidget(view)
        view._on_file_system_changed()
        mock_run.assert_not_called()
