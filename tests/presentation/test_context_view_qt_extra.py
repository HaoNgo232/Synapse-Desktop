"""
Tests cho ContextViewQt.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QMainWindow, QStatusBar
from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.views.context.context_view_qt import ContextViewQt


class DummySettingsService:
    def __init__(self) -> None:
        self._settings = AppSettings(model_id="gpt-5.1", use_gitignore=True)

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: str) -> None:
        setattr(self._settings, key, value)


@pytest.fixture(autouse=True)
def setup_settings_registry():
    orig_service = None
    orig_provider = None
    orig_watcher = None
    orig_preset_factory = None
    orig_cache = None
    try:
        orig_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass
    try:
        orig_provider = DomainRegistry._settings_provider
    except AttributeError:
        pass
    try:
        orig_watcher = DomainRegistry.file_watcher_service()
    except RuntimeError:
        pass
    try:
        orig_preset_factory = DomainRegistry._preset_store_factory
    except AttributeError:
        pass
    try:
        orig_cache = DomainRegistry.cache_registry()
    except RuntimeError:
        pass

    service = DummySettingsService()
    DomainRegistry.register_settings_service(service)
    DomainRegistry.register_settings_provider(lambda: service.load_settings())

    watcher = MagicMock()
    DomainRegistry.register_file_watcher_service(watcher)

    mock_preset_store = MagicMock()
    mock_preset_store.list_presets.return_value = []
    mock_preset_store.to_absolute_paths.side_effect = lambda x: x
    mock_preset_factory = MagicMock()
    mock_preset_factory.create_preset_store.return_value = mock_preset_store
    DomainRegistry.register_preset_store_factory(mock_preset_factory)

    mock_cache = MagicMock()
    DomainRegistry.register_cache_registry(mock_cache)

    yield service, watcher, mock_cache

    if orig_service is not None:
        DomainRegistry.register_settings_service(orig_service)
    DomainRegistry._settings_provider = orig_provider
    if orig_watcher is not None:
        DomainRegistry.register_file_watcher_service(orig_watcher)
    DomainRegistry._preset_store_factory = orig_preset_factory
    if orig_cache is not None:
        DomainRegistry.register_cache_registry(orig_cache)
    else:
        DomainRegistry._cache_registry = None


def test_context_view_initialization(qtbot):
    get_ws = lambda: Path("/mock/workspace")
    view = ContextViewQt(get_workspace=get_ws)
    qtbot.addWidget(view)
    view.show()

    assert view.get_workspace_path() == Path("/mock/workspace")
    assert view._instructions_field.toPlainText() == ""
    assert view.get_selected_paths() == set()


def test_context_view_restore_tree_state(qtbot, tmp_path):
    get_ws = lambda: tmp_path
    view = ContextViewQt(get_workspace=get_ws)
    qtbot.addWidget(view)
    view.show()

    # Create dummy files
    f1 = tmp_path / "file1.py"
    f1.write_text("print(1)")
    d1 = tmp_path / "folder1"
    d1.mkdir()

    # Register custom scanner returning correct tree
    from domain.ports.registry import DomainRegistry
    from domain.smart_context.tree_item import TreeItem
    
    class TestDirectoryScanner:
        def scan_directory(self, root_path: Path) -> TreeItem:
            root = TreeItem(label="root", path=str(root_path), is_dir=True)
            f1_item = TreeItem(label="file1.py", path=str(root_path / "file1.py"), is_dir=False)
            d1_item = TreeItem(label="folder1", path=str(root_path / "folder1"), is_dir=True)
            root.children = [f1_item, d1_item]
            return root

        def scan_directory_shallow(self, root_path, ignore_engine, depth=1, excluded_patterns=None):
            return self.scan_directory(root_path)

        def load_folder_children(self, node, ignore_engine, excluded_patterns=None, use_gitignore=True, workspace_root=None):
            pass

    old_scanner = DomainRegistry.directory_scanner()
    DomainRegistry.register_directory_scanner(TestDirectoryScanner())

    try:
        # Load workspace first so file tree model is populated
        view.on_workspace_changed(tmp_path)

        # Restore state
        view.restore_tree_state(selected_files=[str(f1)], expanded_folders=[str(d1)])
        # verify
        assert str(f1) in view.file_tree_widget.get_selected_paths()
    finally:
        DomainRegistry.register_directory_scanner(old_scanner)



def test_context_view_instructions(qtbot):
    get_ws = lambda: Path("/mock/workspace")
    view = ContextViewQt(get_workspace=get_ws)
    qtbot.addWidget(view)

    view.set_instructions_text("instruction test text")
    assert view.get_instructions_text() == "instruction test text"

    # Change trigger
    view._instructions_field.setPlainText("hello world test")
    # trigger slot
    view._on_instructions_changed()
    assert view._word_count_label.text() == "3 words"


def test_context_view_workspace_changed(qtbot, tmp_path, setup_settings_registry):
    _, watcher, mock_cache = setup_settings_registry
    get_ws = MagicMock(return_value=tmp_path)
    view = ContextViewQt(get_workspace=get_ws)
    qtbot.addWidget(view)
    view.show()

    # Trigger workspace changed
    new_ws = tmp_path / "new_workspace"
    new_ws.mkdir()

    view.on_workspace_changed(new_ws)

    # Watcher should be stopped and restarted for new workspace
    watcher.stop.assert_called_once()
    watcher.start.assert_called_once()
    mock_cache.invalidate_for_workspace.assert_called_once()


def test_context_view_show_copy_breakdown(qtbot):
    get_ws = lambda: Path("/mock/workspace")
    view = ContextViewQt(get_workspace=get_ws)

    # We need a status bar to test StatusBar messages
    main_window = QMainWindow()
    status_bar = QStatusBar()
    main_window.setStatusBar(status_bar)
    # Add view to main window
    main_window.setCentralWidget(view)
    qtbot.addWidget(main_window)
    main_window.show()

    breakdown = {
        "content_tokens": 1000,
        "instruction_tokens": 500,
        "tree_tokens": 100,
        "copy_mode": "Full Copy",
    }

    with patch("presentation.components.toast.toast_qt.toast_success") as mock_toast:
        view.show_copy_breakdown(1600, breakdown)
        mock_toast.assert_called_once()
        assert "1,600 tokens" in status_bar.currentMessage()


def test_context_view_cleanup(qtbot, setup_settings_registry):
    _, watcher, _ = setup_settings_registry
    get_ws = lambda: Path("/mock/workspace")
    view = ContextViewQt(get_workspace=get_ws)
    qtbot.addWidget(view)

    # Setup some dummy states to cleanup
    view._ai_suggest_worker = MagicMock()

    view.cleanup()

    assert view._ai_suggest_worker is None
    watcher.stop.assert_called_once()
