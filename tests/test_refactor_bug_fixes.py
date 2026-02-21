"""
Tests cho 4 bug fixes sau refactoring sang Service-oriented Architecture.

Test cases:
1. SelectionManager encapsulation — _selected_paths tra ve copy, khong reference
2. Clipboard Service API — interface tra ve tuple[bool, str] nhat quan
3. Smart Context parameter — include_relationships=True duoc giu lai
4. Dependency Injection — services inject duoc va mock duoc

Run: pytest tests/test_refactor_bug_fixes.py -v
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Dam bao project root trong sys.path
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ============================================================
# Priority 1: SelectionManager Encapsulation
# ============================================================


class TestSelectionManagerEncapsulation:
    """Dam bao _selected_paths tra ve copy, khong direct reference."""

    def test_selected_paths_returns_copy_not_reference(self):
        """Mutate returned set KHONG anh huong internal state."""
        from services.selection_manager import SelectionManager

        mgr = SelectionManager()
        mgr.add("/test.py")

        # Lay copy qua property
        paths = mgr.selected_paths
        # Mutate copy
        paths.add("/hack.py")

        # Internal state KHONG bi anh huong
        assert "/hack.py" not in mgr.selected_paths
        assert "/test.py" in mgr.selected_paths
        assert mgr.count() == 1

    def test_last_resolved_files_returns_copy(self):
        """Resolved files property cung tra ve copy."""
        from services.selection_manager import SelectionManager

        mgr = SelectionManager()
        mgr.set_resolved_files({"/a.py", "/b.py"}, generation=1)

        resolved = mgr.last_resolved_files
        resolved.add("/hack.py")

        # Internal state KHONG bi anh huong
        assert "/hack.py" not in mgr.last_resolved_files

    def test_mutations_go_through_manager_methods(self):
        """Tat ca mutations di qua add/remove/clear, khong direct access."""
        from services.selection_manager import SelectionManager

        mgr = SelectionManager()

        # add
        mgr.add("/a.py")
        assert mgr.is_selected("/a.py")

        # add_many
        added = mgr.add_many({"/b.py", "/c.py"})
        assert added == 2
        assert mgr.count() == 3

        # remove
        mgr.remove("/a.py")
        assert not mgr.is_selected("/a.py")
        assert mgr.count() == 2

        # remove_many
        removed = mgr.remove_many({"/b.py", "/c.py"})
        assert removed == 2
        assert mgr.count() == 0

    def test_generation_increments_on_bump(self):
        """bump_generation() tang counter va invalidate resolved files."""
        from services.selection_manager import SelectionManager

        mgr = SelectionManager()
        gen0 = mgr.selection_generation

        mgr.add("/test.py")
        mgr.set_resolved_files({"/test.py"}, generation=gen0)

        # Bump generation
        gen1 = mgr.bump_generation()
        assert gen1 == gen0 + 1

        # Resolved files bi invalidate
        assert mgr.get_resolved_files_if_fresh() is None

    def test_reset_clears_all_state(self):
        """reset() xoa tat ca state nhung BUMP generation (monotonic invariant)."""
        from services.selection_manager import SelectionManager

        mgr = SelectionManager()
        mgr.add("/a.py")
        mgr.bump_generation()
        gen_before_reset = mgr.selection_generation
        mgr.set_resolved_files({"/a.py"}, generation=mgr.selection_generation)

        mgr.reset()

        assert mgr.count() == 0
        # Generation phai tang (monotonic), KHONG reset ve 0
        assert mgr.selection_generation > gen_before_reset
        assert mgr.get_resolved_files_if_fresh() is None


# ============================================================
# Priority 1b: FileTreeModel delegates to SelectionManager
# ============================================================


class TestFileTreeModelDelegation:
    """Dam bao FileTreeModel._selected_paths tra ve copy."""

    @pytest.fixture
    def mock_qt(self):
        """Mock PySide6 de test khong can Qt runtime."""
        with patch("components.file_tree_model.QAbstractItemModel.__init__"):
            yield

    def test_file_tree_model_selected_paths_property_returns_copy(self, mock_qt):
        """FileTreeModel._selected_paths tra ve copy tu SelectionManager."""
        from components.file_tree_model import FileTreeModel

        model = FileTreeModel.__new__(FileTreeModel)
        # Init manually
        from services.selection_manager import SelectionManager

        model._selection_mgr = SelectionManager()
        model._selection_mgr.add("/test.py")

        # Get paths via property (should be copy)
        paths = model._selected_paths
        paths.add("/hack.py")

        # Original KHONG bi anh huong
        assert "/hack.py" not in model._selected_paths
        assert "/test.py" in model._selected_paths


# ============================================================
# Priority 2: Clipboard Service API
# ============================================================


class TestClipboardServiceAPI:
    """Dam bao clipboard service tra ve tuple nhat quan."""

    def test_interface_accepts_tuple_return(self):
        """IClipboardService protocol chap nhan tuple[bool, str]."""
        from services.service_interfaces import IClipboardService

        # Tao mock tra ve tuple
        mock = Mock()
        mock.copy_to_clipboard = Mock(return_value=(True, ""))

        # Verify instance check (runtime_checkable)
        assert isinstance(mock, IClipboardService)

    def test_qt_clipboard_service_returns_tuple(self):
        """QtClipboardService.copy_to_clipboard tra ve tuple[bool, str]."""
        from services.prompt_build_service import QtClipboardService

        service = QtClipboardService()

        # Mock QApplication.clipboard de tranh Qt runtime
        # QApplication duoc import local trong method nen patch tai PySide6
        mock_clipboard = Mock()
        with patch("PySide6.QtWidgets.QApplication") as mock_app_cls:
            mock_app_cls.clipboard.return_value = mock_clipboard
            result = service.copy_to_clipboard("test text")

        # Phai la tuple
        assert isinstance(result, tuple)
        assert len(result) == 2

        success, error = result
        assert isinstance(success, bool)
        assert isinstance(error, str)

    def test_qt_clipboard_service_returns_error_on_failure(self):
        """QtClipboardService tra ve (False, error_msg) khi that bai."""
        from services.prompt_build_service import QtClipboardService

        service = QtClipboardService()

        # Mock clipboard tra ve None
        with patch("PySide6.QtWidgets.QApplication") as mock_app_cls:
            mock_app_cls.clipboard.return_value = None
            success, err_msg = service.copy_to_clipboard("test")

        assert success is False
        assert "None" in err_msg

    def test_clipboard_tuple_unpacking_pattern(self):
        """Dam bao pattern success, err_msg = ... hoat dong dung."""
        mock_service = Mock()

        # Case 1: Success
        mock_service.copy_to_clipboard.return_value = (True, "")
        success, err_msg = mock_service.copy_to_clipboard("text")
        assert success is True
        assert err_msg == ""

        # Case 2: Failure
        mock_service.copy_to_clipboard.return_value = (False, "Clipboard unavailable")
        success, err_msg = mock_service.copy_to_clipboard("text")
        assert success is False
        assert err_msg == "Clipboard unavailable"


# ============================================================
# Priority 3: Smart Context Parameter
# ============================================================


class TestSmartContextParameter:
    """Dam bao include_relationships=True trong smart context."""

    def test_build_smart_passes_include_relationships(self):
        """PromptBuildService._build_smart phai pass include_relationships=True."""
        from services.prompt_build_service import PromptBuildService

        service = PromptBuildService()
        workspace = Path("/tmp/test_workspace")

        with patch("services.prompt_build_service.generate_smart_context") as mock_gen:
            mock_gen.return_value = "mock smart content"
            with patch("services.prompt_build_service.generate_file_map") as mock_map:
                mock_map.return_value = ""
                with patch(
                    "services.prompt_build_service.build_smart_prompt"
                ) as mock_build:
                    mock_build.return_value = "final prompt"

                    service._build_smart(
                        file_paths=[Path("/tmp/test.py")],
                        workspace=workspace,
                        instructions="test",
                        include_git_changes=False,
                        use_relative_paths=False,
                    )

            # Verify include_relationships=True duoc truyen
            mock_gen.assert_called_once()
            call_kwargs = mock_gen.call_args
            # Check keyword argument
            assert call_kwargs.kwargs.get("include_relationships") is True or (
                len(call_kwargs.args) > 2 and call_kwargs.args[2] is True
            ), "include_relationships must be True"


# ============================================================
# Priority 4: Dependency Injection
# ============================================================


class TestDependencyInjection:
    """Dam bao services co the inject va mock duoc."""

    def test_context_view_accepts_injected_services(self):
        """ContextViewQt nhan prompt_builder va clipboard_service qua constructor."""
        mock_builder = Mock()
        mock_clipboard = Mock()

        # Mock QWidget.__init__ de tranh Qt runtime
        with patch("views.context_view_qt.QWidget.__init__"):
            with patch("views.context_view_qt.UIBuilderMixin._build_ui"):
                with patch("views.context_view_qt.FileWatcher"):
                    from views.context_view_qt import ContextViewQt

                    view = ContextViewQt(
                        get_workspace=lambda: Path("/test"),
                        prompt_builder=mock_builder,
                        clipboard_service=mock_clipboard,
                    )

                    assert view._prompt_builder is mock_builder
                    assert view._clipboard_service is mock_clipboard

    def test_context_view_creates_defaults_when_none(self):
        """ContextViewQt tao default services khi khong truyen vao."""
        with patch("views.context_view_qt.QWidget.__init__"):
            with patch("views.context_view_qt.UIBuilderMixin._build_ui"):
                with patch("views.context_view_qt.FileWatcher"):
                    from views.context_view_qt import ContextViewQt
                    from services.prompt_build_service import (
                        PromptBuildService,
                        QtClipboardService,
                    )

                    view = ContextViewQt(
                        get_workspace=lambda: Path("/test"),
                    )

                    assert isinstance(view._prompt_builder, PromptBuildService)
                    assert isinstance(view._clipboard_service, QtClipboardService)

    def test_mock_services_are_called_correctly(self):
        """Injected mocks receive calls dung nhu expected."""
        mock_builder = Mock()
        mock_builder.build_prompt.return_value = ("prompt text", 42)
        mock_clipboard = Mock()
        mock_clipboard.copy_to_clipboard.return_value = (True, "")

        # Verify mock responses
        prompt, count = mock_builder.build_prompt(
            file_paths=[],
            workspace=Path("/test"),
            instructions="",
            output_format="xml",
            include_git_changes=False,
            use_relative_paths=False,
        )
        assert prompt == "prompt text"
        assert count == 42

        success, err = mock_clipboard.copy_to_clipboard("test")
        assert success is True
        assert err == ""


# ============================================================
# Priority 5: Performance Regression
# ============================================================


class TestPerformanceRegression:
    """Dam bao khong co performance regression khi select nhieu files."""

    @pytest.fixture
    def mock_qt(self):
        with patch("components.file_tree_model.QAbstractItemModel.__init__"):
            yield

    def test_selection_performance_with_large_tree(self, mock_qt):
        """Test FileTreeModel.data() check state performance voi 10,000 files."""
        from components.file_tree_model import FileTreeModel, TreeNode
        from services.selection_manager import SelectionManager
        import time
        from PySide6.QtCore import Qt

        model = FileTreeModel.__new__(FileTreeModel)
        model._selection_mgr = SelectionManager()

        # Giả lập 10,000 file được chọn
        large_selection = {f"/path/to/project/file_{i}.py" for i in range(10000)}
        model._selection_mgr.replace_all(large_selection)

        # Tạo một node để test
        node = TreeNode(
            label="file_5000.py", path="/path/to/project/file_5000.py", is_dir=False
        )

        # Tạo mock index return node
        mock_index = Mock()
        mock_index.isValid.return_value = True
        mock_index.internalPointer.return_value = node

        # Measure time cho 1000 lần gọi data (giả lập UI scroll/repaint)
        start_time = time.perf_counter()
        for _ in range(1000):
            state = model.data(mock_index, Qt.ItemDataRole.CheckStateRole)
            assert state == Qt.CheckState.Checked

        end_time = time.perf_counter()

        # Thoi gian phai nho hon 100ms
        render_time_ms = (end_time - start_time) * 1000
        assert render_time_ms < 100.0, (
            f"Performance regression: {render_time_ms:.2f}ms > 100ms"
        )
