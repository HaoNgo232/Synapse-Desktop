"""Cau hinh pytest-qt cho UI tests.

Tat exception capture cho Qt event loop de tranh false failures
tu cac signal orphan giua cac test fixtures.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal

from presentation.views.context.context_view_qt import ContextViewQt


class SyncDebouncedTimer:
    def __init__(self, interval_ms, callback, parent=None):
        self.callback = callback
    def start(self, interval_ms=None):
        self.callback()
    def stop(self):
        pass
    def is_active(self):
        return False


class FakeFileTreeWidget(QWidget):
    """Fake FileTreeWidget thay the cho testing, chua cac signal can thiet."""

    selection_changed = Signal(set)
    file_preview_requested = Signal(str)
    token_counting_done = Signal()
    exclude_patterns_changed = Signal()

    def __init__(self, *args, **kwargs):
        # Allow any arguments like ignore_engine, tokenization_service when mocked
        super().__init__()

    def get_model(self):
        mock_model = MagicMock()
        mock_model.get_selected_file_count.return_value = 0
        mock_model._root_node = None
        return mock_model

    def load_tree(self, path):
        pass

    def get_selected_paths(self):
        return []

    def get_expanded_paths(self):
        return []

    def get_total_tokens(self):
        return 0

    def get_total_files(self):
        return 0

    def get_all_selected_paths(self):
        return set()

    def remove_paths_from_selection(self, paths):
        return len(paths)

    def add_paths_to_selection(self, paths):
        pass

    def set_selected_paths(self, paths):
        pass

    def set_expanded_paths(self, paths):
        pass


class FakeTokenStatsPanel(QWidget):
    """Fake TokenStatsPanelQt cho testing."""

    model_changed = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()

    def update_stats(self, **kwargs):
        pass


@pytest.fixture(autouse=True)
def _no_qt_exception_capture(request):
    """Tat Qt exception capture cho tat ca UI tests.

    PySide6 co the fire signals trong event loop thong qua
    deferred connections hoac timer callbacks tu widgets da bi
    destroy boi test truoc. Dieu nay gay ra false CALL ERROR
    trong pytest-qt.
    """
    if hasattr(request, "node"):
        marker = pytest.mark.qt_no_exception_capture
        request.node.add_marker(marker)


@pytest.fixture(autouse=True)
def reset_toast_manager():
    """Tự động reset singleton ToastManager trước và sau mỗi test để tránh rò rỉ C++ parent widget đã bị giải phóng."""
    try:
        from presentation.components.toast.toast_qt import ToastManager

        ToastManager._instance = None
    except ImportError:
        pass
    yield
    try:
        from presentation.components.toast.toast_qt import ToastManager

        ToastManager._instance = None
    except ImportError:
        pass


@pytest.fixture
def context_view(qtbot):
    """Fixture tao ContextViewQt voi dependencies da mock."""
    mock_prompt_builder = MagicMock()
    mock_prompt_builder.count_tokens.return_value = 0
    mock_clipboard_service = MagicMock()

    mock_app_settings = MagicMock()
    mock_app_settings.output_format = "xml"
    mock_app_settings.copy_mode = "full"
    mock_app_settings.tree_map_only = False
    mock_app_settings.git_commit_depth = 0
    mock_app_settings.include_git_changes = False
    mock_app_settings.include_full_tree = False
    mock_app_settings.excluded_folders = ""
    mock_app_settings.rule_file_names = []

    with (
        patch(
            "presentation.views.context.ui_builder.FileTreeWidget", FakeFileTreeWidget
        ),
        patch(
            "presentation.views.context.ui_builder.TokenStatsPanelQt",
            FakeTokenStatsPanel,
        ),
        patch(
            "presentation.views.context.ui_builder.load_app_settings",
            return_value=mock_app_settings,
        ),
        patch("domain.prompt.template_manager.list_templates", return_value=[]),
        patch(
            "presentation.views.context.context_view_qt.FileWatcher",
            return_value=MagicMock(),
        ),
        patch(
            "presentation.views.context.context_view_qt.DebouncedTimer",
            SyncDebouncedTimer,
        ),
        patch(
            "presentation.views.context.related_files_controller.DebouncedTimer",
            SyncDebouncedTimer,
        ),
    ):
        view = ContextViewQt(
            get_workspace=lambda: Path("/fake/workspace"),
            prompt_builder=mock_prompt_builder,
            clipboard_service=mock_clipboard_service,
        )
        qtbot.addWidget(view)
        yield view
