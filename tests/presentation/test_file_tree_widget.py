"""
Tests cho FileTreeWidget - widget tích hợp file tree model, filter và delegate.
"""

import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import QModelIndex

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.components.file_tree.file_tree_widget import FileTreeWidget
from presentation.components.file_tree.file_tree_model import FileTreeModel


# ===========================================================================
# Fixtures
# ===========================================================================


class DummySettingsService:
    def __init__(self) -> None:
        self._settings = AppSettings()

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: str) -> None:
        setattr(self._settings, key, value)


@pytest.fixture(autouse=True)
def setup_registry():
    orig_service = None
    orig_provider = None
    try:
        orig_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass
    try:
        orig_provider = DomainRegistry._settings_provider
    except AttributeError:
        pass

    service = DummySettingsService()
    DomainRegistry.register_settings_service(service)
    DomainRegistry.register_settings_provider(lambda: service.load_settings())

    yield service

    if orig_service is not None:
        DomainRegistry.register_settings_service(orig_service)
    DomainRegistry._settings_provider = orig_provider


@pytest.fixture()
def widget(qtbot):
    ignore_engine = MagicMock()
    ignore_engine.should_ignore.return_value = False
    tokenization_service = MagicMock()
    tokenization_service.count_tokens.return_value = 10

    w = FileTreeWidget(
        ignore_engine=ignore_engine,
        tokenization_service=tokenization_service,
    )
    qtbot.addWidget(w)
    return w


@pytest.fixture()
def widget_with_tree(widget, tmp_path):
    (tmp_path / "main.py").write_text("def main(): pass\n" * 10)
    (tmp_path / "utils.py").write_text("def util(): pass\n")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "helper.py").write_text("def help(): pass\n")

    widget.load_tree(tmp_path)
    return widget, tmp_path


# ===========================================================================
# Basic Initialization
# ===========================================================================


def test_widget_creates_successfully(widget):
    assert widget is not None
    assert widget._model is not None
    assert widget._filter_proxy is not None


def test_widget_has_search_field(widget):
    assert widget._search_field is not None
    assert widget._search_field.placeholderText() == "Search files..."


def test_widget_has_action_buttons(widget):
    assert widget._select_all_btn is not None
    assert widget._deselect_all_btn is not None
    assert widget._collapse_btn is not None
    assert widget._expand_btn is not None


def test_widget_has_tree_view(widget):
    assert widget._tree_view is not None


# ===========================================================================
# Public API Tests
# ===========================================================================


def test_widget_get_selected_paths_empty(widget):
    paths = widget.get_selected_paths()
    assert paths == []


def test_widget_get_all_selected_paths_empty(widget):
    paths = widget.get_all_selected_paths()
    assert isinstance(paths, set)
    assert len(paths) == 0


def test_widget_get_root_tree_item_before_load(widget):
    item = widget.get_root_tree_item()
    assert item is None


def test_widget_get_model(widget):
    model = widget.get_model()
    assert isinstance(model, FileTreeModel)


def test_widget_get_total_tokens_empty(widget):
    total = widget.get_total_tokens()
    assert total == 0


def test_widget_get_search_results_empty(widget):
    results = widget.get_search_results()
    assert isinstance(results, list)
    assert len(results) == 0


def test_widget_get_expanded_paths_before_load(widget):
    expanded = widget.get_expanded_paths()
    assert isinstance(expanded, list)


def test_widget_load_tree(widget_with_tree):
    widget, tmp_path = widget_with_tree
    # After load, root tree item should be set
    root = widget.get_root_tree_item()
    assert root is not None


def test_widget_set_selected_paths(widget_with_tree, tmp_path):
    widget, tmp_path = widget_with_tree
    f = str(tmp_path / "main.py")
    widget.set_selected_paths({f})
    all_paths = widget.get_all_selected_paths()
    assert f in all_paths


def test_widget_add_paths_to_selection(widget_with_tree, tmp_path):
    widget, tmp_path = widget_with_tree
    f = str(tmp_path / "utils.py")
    added = widget.add_paths_to_selection({f})
    assert added >= 0
    all_paths = widget.get_all_selected_paths()
    assert f in all_paths


def test_widget_remove_paths_from_selection(widget_with_tree, tmp_path):
    widget, tmp_path = widget_with_tree
    f = str(tmp_path / "main.py")
    widget.set_selected_paths({f})
    removed = widget.remove_paths_from_selection({f})
    assert removed >= 0
    all_paths = widget.get_all_selected_paths()
    assert f not in all_paths


def test_widget_clear_token_cache(widget_with_tree):
    widget, _ = widget_with_tree
    # Should not raise
    widget.clear_token_cache()
    assert widget.get_total_tokens() == 0


def test_widget_cleanup(widget):
    # Should not raise
    widget.cleanup()


# ===========================================================================
# Search Functionality
# ===========================================================================


def test_widget_search_updates_filter(widget_with_tree, qtbot):
    widget, tmp_path = widget_with_tree
    # Set search text
    widget._search_field.setText("main")
    # Debounce is 150ms, wait 300ms to be safe
    qtbot.wait(300)
    # Search state should be updated
    assert widget._filter_proxy.search_query == "main"


def test_widget_search_clear(widget_with_tree, qtbot):
    widget, tmp_path = widget_with_tree
    widget._search_field.setText("main")
    qtbot.wait(100)
    widget._search_field.setText("")
    qtbot.wait(100)
    assert widget._filter_proxy.search_query == ""


def test_widget_search_return_pressed(widget_with_tree, qtbot):
    widget, tmp_path = widget_with_tree
    widget._search_field.setText("main")
    # Trigger return press
    widget._on_search_return_pressed()
    # Just verify it does not raise


# ===========================================================================
# Button Actions
# ===========================================================================


def test_widget_select_all_button(widget_with_tree, qtbot):
    widget, tmp_path = widget_with_tree
    widget._select_all_btn.click()
    # After select all, should have some selected paths
    all_paths = widget.get_all_selected_paths()
    assert len(all_paths) > 0


def test_widget_deselect_all_button(widget_with_tree, qtbot):
    widget, tmp_path = widget_with_tree
    widget._select_all_btn.click()  # First select all
    widget._deselect_all_btn.click()  # Then deselect all
    all_paths = widget.get_all_selected_paths()
    assert len(all_paths) == 0


def test_widget_collapse_all_button(widget_with_tree, qtbot):
    widget, tmp_path = widget_with_tree
    widget._collapse_btn.click()
    # Should not raise


def test_widget_expand_all_button(widget_with_tree, qtbot):
    widget, tmp_path = widget_with_tree
    # Expand limited to avoid infinite expand on deep trees
    widget._expand_btn.click()
    qtbot.wait(100)
    # Should not raise


# ===========================================================================
# Model-level interaction via widget
# ===========================================================================


def test_widget_selection_signal_emitted(widget_with_tree, qtbot):
    widget, tmp_path = widget_with_tree
    received_signals: list = []
    widget._model.selection_changed.connect(lambda s: received_signals.append(s))

    # Trigger selection via set_selected_paths
    f = str(tmp_path / "main.py")
    widget.set_selected_paths({f})

    assert len(received_signals) > 0
    assert f in received_signals[-1]


def test_widget_set_expanded_paths(widget_with_tree, qtbot):
    widget, tmp_path = widget_with_tree
    sub = str(tmp_path / "sub")
    widget.set_expanded_paths({sub})
    qtbot.wait(100)
    # Should not raise; expanded state may or may not persist after lazy loading
    expanded = widget.get_expanded_paths()
    assert isinstance(expanded, list)


# ===========================================================================
# On Model Selection Changed
# ===========================================================================


def test_on_model_selection_changed(widget_with_tree):
    widget, tmp_path = widget_with_tree
    # Simulate model selection changed signal
    f = str(tmp_path / "main.py")
    widget._on_model_selection_changed({f})
    # Should sync selection without error


def test_on_select_search_results_no_results(widget):
    # When no search results, clicking select results should not error
    widget._on_select_search_results()


def test_on_select_search_results_with_results(widget_with_tree, tmp_path, qtbot):
    widget, tmp_path = widget_with_tree
    f = str(tmp_path / "main.py")
    widget._last_search_results = [f]
    widget._on_select_search_results()
    qtbot.wait(50)


# ===========================================================================
# Expanded Paths collection
# ===========================================================================


def test_collect_expanded_empty(widget):
    result = []
    widget._collect_expanded(QModelIndex(), result)
    assert result == []


def test_widget_has_close_workspace_button(widget):
    assert widget._close_workspace_btn is not None


def test_is_loading_tree_prevents_selection_write(widget_with_tree):
    widget, tmp_path = widget_with_tree
    
    # Ghi nhận trạng thái lúc bình thường
    assert widget._is_loading_tree is False
    
    # Mocking self._write_agent_selection để kiểm tra xem có bị gọi không
    original_write = widget._write_agent_selection
    mock_write = MagicMock()
    widget._write_agent_selection = mock_write
    
    # 1. Khi load_tree chạy, flag _is_loading_tree được kích hoạt
    # Chúng ta verify rằng trong suốt quá trình load_tree, nếu _write_agent_selection được gọi,
    # nó sẽ return sớm nhờ _is_loading_tree.
    widget._is_loading_tree = True
    widget._write_agent_selection({"test_path"})
    
    # Vì mock_write được gọi nhưng bên trong _write_agent_selection nguyên bản
    # sẽ return sớm khi _is_loading_tree = True, hãy verify logic này gián tiếp qua
    # việc gọi hàm thật với flag.
    # Khôi phục hàm thật để test logic của nó
    widget._write_agent_selection = original_write
    
    # Tạo mock cho json.dump hoặc os.replace để verify nó không chạy ghi IO xuống disk
    import os
    original_replace = os.replace
    mock_replace = MagicMock()
    os.replace = mock_replace
    
    try:
        # Khi flag = True: Không được ghi xuống disk
        widget._is_loading_tree = True
        widget._write_agent_selection({str(tmp_path / "main.py")})
        mock_replace.assert_not_called()
        
        # Khi flag = False: Phải ghi xuống disk
        widget._is_loading_tree = False
        widget._write_agent_selection({str(tmp_path / "main.py")})
        mock_replace.assert_called_once()
    finally:
        os.replace = original_replace

