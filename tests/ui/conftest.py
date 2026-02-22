"""Cau hinh pytest-qt cho UI tests.

Tat exception capture cho Qt event loop de tranh false failures
tu cac signal orphan giua cac test fixtures.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal

from views.context_view_qt import ContextViewQt


class FakeFileTreeWidget(QWidget):
    """Fake FileTreeWidget thay the cho testing, chua cac signal can thiet."""

    selection_changed = Signal(set)
    file_preview_requested = Signal(str)
    token_counting_done = Signal()

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


class FakeTokenStatsPanel(QWidget):
    """Fake TokenStatsPanelQt cho testing."""

    model_changed = Signal(str)

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


@pytest.fixture
def context_view(qtbot):
    """Fixture tao ContextViewQt voi dependencies da mock."""
    mock_prompt_builder = MagicMock()
    mock_prompt_builder.count_tokens.return_value = 0
    mock_clipboard_service = MagicMock()

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
        view = ContextViewQt(
            get_workspace=lambda: Path("/fake/workspace"),
            prompt_builder=mock_prompt_builder,
            clipboard_service=mock_clipboard_service,
        )
        qtbot.addWidget(view)
        yield view
