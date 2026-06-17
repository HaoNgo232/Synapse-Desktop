"""
GUI/Unit Tests cho các controller điều phối giao diện trong context view:
TreeManagementController, RelatedFilesController, và CopyActionController.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Set, List, Optional, Any

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QWidget, QMessageBox, QDialog

from domain.ports.registry import DomainRegistry
from presentation.views.context.tree_management_controller import (
    TreeManagementController,
    TreeManagementViewProtocol,
)
from presentation.views.context.related_files_controller import (
    RelatedFilesController,
    RelatedFilesViewProtocol,
)
from presentation.views.context.copy_action_controller import (
    CopyActionController,
    CopyActionViewProtocol,
    PromptCache,
    _build_fingerprint,
    copy_as_file_to_clipboard,
)

# ===========================================================================
# Fixture Mocking Qt Threading & Async patterns
# ===========================================================================


@pytest.fixture(autouse=True)
def mock_qt_threading():
    """Chuyển đổi chạy background thread thành chạy đồng bộ để test ổn định."""
    # Mock cho RelatedFilesController
    with (
        patch(
            "presentation.views.context.related_files_controller.schedule_background",
            lambda f: f(),
        ),
        patch(
            "presentation.views.context.related_files_controller.run_on_main_thread",
            lambda f: f(),
        ),
        patch(
            "presentation.views.context.tree_management_controller.run_on_main_thread",
            lambda f: f(),
        ),
        patch("presentation.utils.qt_utils.run_on_main_thread", lambda f: f()),
        patch("presentation.utils.qt_utils.schedule_background", lambda f: f()),
    ):
        # Chạy đồng bộ QThreadPool.start(worker)
        def start_mock(self, worker):
            worker.run()
            return True

        with patch.object(QThreadPool, "start", start_mock):
            yield


# ===========================================================================
# 1. TreeManagementController Tests
# ===========================================================================


class MockTreeManagementView(TreeManagementViewProtocol):
    def __init__(self):
        self.workspace = Path("/mock/workspace")
        self.selected_paths = set()
        self.expanded_paths = []
        self.loaded_tree_path = None
        self.restored_state = None
        self.changed_workspace = None
        self.statuses = []
        self.prompt_cache_invalidated = False

    def get_workspace(self) -> Optional[Path]:
        return self.workspace

    def get_all_selected_paths(self) -> Set[str]:
        return self.selected_paths

    def get_expanded_paths(self) -> List[str]:
        return self.expanded_paths

    def load_tree(self, workspace: Path) -> None:
        self.loaded_tree_path = workspace

    def restore_tree_state(
        self, selected_files: List[str], expanded_folders: List[str]
    ) -> None:
        self.restored_state = (selected_files, expanded_folders)

    def on_workspace_changed(self, workspace_path: Path) -> None:
        self.changed_workspace = workspace_path

    def show_status(self, message: str, is_error: bool = False) -> None:
        self.statuses.append((message, is_error))

    def invalidate_prompt_cache(self) -> None:
        self.prompt_cache_invalidated = True


def test_tree_management_refresh_tree(qtbot):
    """Test refresh_tree lưu và khôi phục trạng thái."""
    view = MockTreeManagementView()
    controller = TreeManagementController(view)

    view.selected_paths = {"/mock/workspace/file1.py", "/mock/workspace/file2.py"}
    view.expanded_paths = ["/mock/workspace/folder1"]

    controller.refresh_tree()

    assert view.loaded_tree_path == Path("/mock/workspace")
    assert view.restored_state == (
        list(view.selected_paths),
        view.expanded_paths,
    )

    # Test refresh khi không có workspace -> không làm gì
    view.workspace = None
    view.loaded_tree_path = None
    controller.refresh_tree()
    assert view.loaded_tree_path is None


def test_tree_management_add_and_undo_ignore(qtbot):
    """Test thêm ignore pattern và hoàn tác (undo)."""
    view = MockTreeManagementView()
    controller = TreeManagementController(view)

    # Chưa chọn file
    controller.add_to_ignore()
    assert any("No files selected" in s[0] for s in view.statuses)

    # Chọn file để ignore
    view.selected_paths = {"/mock/workspace/file1.py", "/mock/workspace/sub/file2.py"}

    with patch(
        "application.services.workspace_config.add_excluded_patterns", return_value=True
    ) as mock_add:
        controller.add_to_ignore()
        mock_add.assert_called_once()
        assert controller._last_ignored_patterns != []
        assert any("Added" in s[0] for s in view.statuses)

    # Undo ignore
    with patch(
        "application.services.workspace_config.remove_excluded_patterns",
        return_value=True,
    ) as mock_remove:
        controller.undo_ignore()
        mock_remove.assert_called_once()
        removed_patterns = {p.replace('\\', '/') for p in mock_remove.call_args[0][0]}
        assert removed_patterns == {"file1.py", "sub/file2.py"}
        assert controller._last_ignored_patterns == []
        assert any("Removed" in s[0] for s in view.statuses)

    # Undo ignore khi last_ignored_patterns trống
    view.statuses.clear()
    controller.undo_ignore()
    assert any("Nothing to undo" in s[0] for s in view.statuses)


def test_tree_management_dialogs(qtbot):
    """Test mở dialog clone repo và dialog quản lý cache."""
    view = MockTreeManagementView()
    controller = TreeManagementController(view)

    dummy_repo_manager = MagicMock()
    DomainRegistry.register_repo_manager(dummy_repo_manager)

    parent = QWidget()

    # Test open_remote_repo_dialog
    with patch(
        "presentation.components.dialogs.dialogs_qt.RemoteRepoDialogQt"
    ) as mock_dialog_cls:
        mock_instance = MagicMock()
        mock_dialog_cls.return_value = mock_instance

        controller.open_remote_repo_dialog(parent)

        # Verify dialog được tạo với callback success
        mock_dialog_cls.assert_called_once()
        args, kwargs = mock_dialog_cls.call_args
        # Lấy callback clone success
        on_clone_success = args[2]
        on_clone_success(Path("/mock/workspace/cloned"))

        assert view.changed_workspace == Path("/mock/workspace/cloned")
        mock_instance.exec.assert_called_once()

    # Test open_cache_management_dialog
    with patch(
        "presentation.components.dialogs.dialogs_qt.CacheManagementDialogQt"
    ) as mock_dialog_cls:
        mock_instance = MagicMock()
        mock_dialog_cls.return_value = mock_instance

        controller.open_cache_management_dialog(parent)

        mock_dialog_cls.assert_called_once()
        args, kwargs = mock_dialog_cls.call_args
        # Lấy callback open repo
        on_open_repo = args[2]
        on_open_repo(Path("/mock/workspace/cached"))

        assert view.changed_workspace == Path("/mock/workspace/cached")
        mock_instance.exec.assert_called_once()

    controller.cleanup()
    assert controller._repo_manager is None


def test_tree_management_file_watcher_callbacks(qtbot):
    """Test callbacks khi có file thay đổi trên disk."""
    view = MockTreeManagementView()
    controller = TreeManagementController(view)

    # Mock cache registry
    mock_cache = MagicMock()
    DomainRegistry.register_cache_registry(mock_cache)

    # Thêm graph_provider ảo vào view
    view._graph_provider = MagicMock()

    # 1. File modified
    controller.on_file_modified("/mock/workspace/file1.py")
    mock_cache.invalidate_for_path.assert_called_once_with("/mock/workspace/file1.py")
    assert view.prompt_cache_invalidated
    view._graph_provider.on_files_changed.assert_called_once_with(
        ["/mock/workspace/file1.py"]
    )

    # 2. File created
    view._graph_provider.on_files_changed.reset_mock()
    controller.on_file_created("/mock/workspace/new.py")
    view._graph_provider.on_files_changed.assert_called_once_with(
        ["/mock/workspace/new.py"]
    )

    # 3. File deleted
    controller.on_file_deleted("/mock/workspace/deleted.py")
    view._graph_provider.on_files_deleted.assert_called_once_with(
        ["/mock/workspace/deleted.py"]
    )

    # 4. Batch file system changed
    with patch.object(controller, "refresh_tree") as mock_refresh:
        controller.on_file_system_changed()
        mock_refresh.assert_called_once()


# ===========================================================================
# 2. RelatedFilesController Tests
# ===========================================================================


class MockRelatedFilesView(RelatedFilesViewProtocol):
    def __init__(self):
        self.workspace = Path("/mock/workspace")
        self.selected_paths = set()
        self.added_paths = set()
        self.removed_paths = set()
        self.statuses = []
        self.button_text_updates = []

    def get_workspace(self) -> Optional[Path]:
        return self.workspace

    def get_all_selected_paths(self) -> Set[str]:
        return self.selected_paths

    def add_paths_to_selection(self, paths: Set[str]) -> int:
        self.added_paths.update(paths)
        self.selected_paths.update(paths)
        return len(paths)

    def remove_paths_from_selection(self, paths: Set[str]) -> int:
        self.removed_paths.update(paths)
        self.selected_paths.difference_update(paths)
        return len(paths)

    def scan_full_tree(self, workspace: Path) -> Any:
        return {}

    def show_status(self, message: str, is_error: bool = False) -> None:
        self.statuses.append((message, is_error))

    def update_related_button_text(self, active: bool, depth: int, count: int) -> None:
        self.button_text_updates.append((active, depth, count))


def test_related_files_activation_deactivation(qtbot):
    """Test bật, tắt related mode và dọn dẹp selection."""
    view = MockRelatedFilesView()
    controller = RelatedFilesController(view)

    # Kích hoạt
    controller.set_mode(active=True, depth=2)
    assert controller.is_active
    assert controller.depth == 2
    assert view.button_text_updates[-1][0] is True

    # Tắt
    controller._last_added_related_files = {"/mock/workspace/rel.py"}
    controller.set_mode(active=False, depth=2)
    assert not controller.is_active
    assert view.removed_paths == {"/mock/workspace/rel.py"}

    controller.cleanup()


def test_related_files_resolving(qtbot):
    """Test giải quyết files liên quan (resolve related files)."""
    view = MockRelatedFilesView()
    controller = RelatedFilesController(view)

    # Đặt selection ban đầu
    view.selected_paths = {"/mock/workspace/main.py"}

    # Giả lập file Python hợp lệ
    with (
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.is_dir", return_value=False),
    ):
        # Bật mode
        controller.set_mode(active=True, depth=1)

        # Test Resolve related files
        with patch(
            "presentation.views.context.related_files_controller.get_related_files_for_paths",
            return_value={"/mock/workspace/helper.py", "/mock/workspace/main.py"},
        ) as mock_get:
            controller.resolve_for_current_selection()

            mock_get.assert_called_once()
            # helper.py phải được thêm vào selection (bỏ qua main.py vì đã chọn)
            assert "/mock/workspace/helper.py" in view.added_paths
            assert controller.related_files_count == 1
            assert any("Found 1 related files" in s[0] for s in view.statuses)

    # Resolve tiếp khi selection trống
    view.selected_paths.clear()
    controller.resolve_for_current_selection()
    assert controller.related_files_count == 0


# ===========================================================================
# 3. CopyActionController Tests
# ===========================================================================


class MockCopyActionView(CopyActionViewProtocol):
    def __init__(self):
        self.workspace = Path("/mock/workspace")
        self.selected_paths = set()
        self.instructions = "Mock instruction"
        self.output_style = MagicMock()
        self.output_style.value = "plain"
        self.statuses = []
        self.copy_breakdowns = []
        self.total_tokens = 100
        self.buttons_enabled = True
        self.clipboard_service = MagicMock()
        self.clipboard_service.copy_to_clipboard.return_value = (True, "")
        self.prompt_builder = MagicMock()
        self.tokenization_service = MagicMock()
        self.ignore_engine = MagicMock()
        self.copy_as_file = False
        self.full_tree = False
        self.smart_mode_active = False
        self.copy_config = MagicMock()
        self.copy_config.include_git_diff = False
        self.copy_config.tree_map_only = False
        self.parent = QWidget()

    def get_workspace(self) -> Optional[Path]:
        return self.workspace

    def get_workspace_path(self) -> Optional[Path]:
        return self.workspace

    def get_selected_paths(self) -> Set[str]:
        return self.selected_paths

    def get_instructions_text(self) -> str:
        return self.instructions

    def get_output_style(self):
        return self.output_style

    def show_status(self, message: str, is_error: bool = False) -> None:
        self.statuses.append((message, is_error))

    def show_copy_breakdown(self, token_count: int, breakdown: dict) -> None:
        self.copy_breakdowns.append((token_count, breakdown))

    def get_total_tokens(self) -> int:
        return self.total_tokens

    def set_copy_buttons_enabled(self, enabled: bool) -> None:
        self.buttons_enabled = enabled

    def get_clipboard_service(self) -> Any:
        return self.clipboard_service

    def get_prompt_builder(self) -> Any:
        return self.prompt_builder

    def scan_full_tree(self, workspace: Path) -> Any:
        return {}

    def parent_widget(self) -> Any:
        return self.parent

    def get_tokenization_service(self) -> Any:
        return self.tokenization_service

    def get_ignore_engine(self) -> Any:
        return self.ignore_engine

    def get_copy_as_file(self) -> bool:
        return self.copy_as_file

    def get_full_tree(self) -> bool:
        return self.full_tree

    def is_smart_mode_active(self) -> bool:
        return self.smart_mode_active

    def get_copy_config(self) -> Any:
        return self.copy_config


def test_prompt_cache():
    """Test PromptCache lưu trữ, lấy và xoá cache."""
    cache = PromptCache()

    # Get cache miss
    assert cache.get("mode-1", "fingerprint-1") is None

    # Put và hit cache
    breakdown = {"files": 10}
    cache.put("mode-1", "fingerprint-1", "prompt-text", 50, breakdown)

    cached = cache.get("mode-1", "fingerprint-1")
    assert cached is not None
    assert cached[0] == "prompt-text"
    assert cached[1] == 50
    assert cached[2] == breakdown

    # Invalidate một mode
    cache.invalidate("mode-1")
    assert cache.get("mode-1", "fingerprint-1") is None

    # Invalidate all
    cache.put("mode-2", "fingerprint-2", "prompt-text-2", 100, {})
    cache.invalidate_all()
    assert cache.get("mode-2", "fingerprint-2") is None


def test_build_fingerprint():
    """Test fingerprint được sinh ra nhất quán."""
    fp1 = _build_fingerprint(
        selected_paths={"/mock/workspace/file1.py"},
        instructions="do X",
        output_style_id="plain",
        copy_mode="context",
        include_git=False,
        use_relative_paths=True,
        workspace=Path("/mock/workspace"),
    )
    fp2 = _build_fingerprint(
        selected_paths={"/mock/workspace/file1.py"},
        instructions="do X",
        output_style_id="plain",
        copy_mode="context",
        include_git=False,
        use_relative_paths=True,
        workspace=Path("/mock/workspace"),
    )
    assert fp1 == fp2

    # Thay đổi mtime -> fingerprint thay đổi
    import pathlib

    orig_stat = pathlib.Path.stat
    orig_posix_stat_stat = (
        pathlib.PosixPath.stat if hasattr(pathlib, "PosixPath") else None
    )
    orig_windows_stat_stat = (
        pathlib.WindowsPath.stat if hasattr(pathlib, "WindowsPath") else None
    )

    mock_stat_val = MagicMock()
    mock_stat_val.st_mtime = 123456.0
    mock_stat_func = MagicMock(return_value=mock_stat_val)

    def apply_mock():
        pathlib.Path.stat = mock_stat_func
        if orig_posix_stat_stat:
            pathlib.PosixPath.stat = mock_stat_func
        if orig_windows_stat_stat:
            pathlib.WindowsPath.stat = mock_stat_func

    def restore_mock():
        pathlib.Path.stat = orig_stat
        if orig_posix_stat_stat:
            pathlib.PosixPath.stat = orig_posix_stat_stat
        if orig_windows_stat_stat:
            pathlib.WindowsPath.stat = orig_windows_stat_stat

    apply_mock()
    try:
        fp3 = _build_fingerprint(
            selected_paths={"/mock/workspace/file1.py"},
            instructions="do X",
            output_style_id="plain",
            copy_mode="context",
            include_git=False,
            use_relative_paths=True,
        )
        mock_stat_val.st_mtime = 999999.0
        fp4 = _build_fingerprint(
            selected_paths={"/mock/workspace/file1.py"},
            instructions="do X",
            output_style_id="plain",
            copy_mode="context",
            include_git=False,
            use_relative_paths=True,
        )
        assert fp3 != fp4
    finally:
        restore_mock()


def test_copy_as_file_to_clipboard(tmp_path):
    """Test ghi clipboard dưới dạng file URI."""
    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        success, path_str = copy_as_file_to_clipboard("content test", "test_file.txt")
        assert success
        assert Path(path_str).exists()
        assert Path(path_str).read_text(encoding="utf-8") == "content test"


def test_copy_action_ask_copy_destination(qtbot):
    """Test dialog chọn đích đến khi copy (Text/File)."""
    view = MockCopyActionView()
    controller = CopyActionController(view)

    # Mock QDialog
    with patch.object(QDialog, "exec", return_value=1):
        dest = controller._ask_copy_destination("Test Title")
        assert dest == "text"

    with patch.object(QDialog, "exec", return_value=2):
        dest = controller._ask_copy_destination("Test Title")
        assert dest == "file"

    with patch.object(QDialog, "exec", return_value=0):
        dest = controller._ask_copy_destination("Test Title")
        assert dest is None


def test_copy_action_cache_hit(qtbot):
    """Test khi hit cache không cần gọi background worker."""
    view = MockCopyActionView()
    controller = CopyActionController(view)

    view.selected_paths = {"/mock/workspace/file1.py"}

    # Thực hiện bọc cả store_in_cache và copy_context trong patch
    with (
        patch("pathlib.Path.is_file", return_value=True),
        patch.object(DomainRegistry, "settings") as mock_settings,
    ):
        mock_settings.return_value.enable_security_check = False
        mock_settings.return_value.include_git_changes = False

        # Ghi dữ liệu giả lập vào cache
        controller._store_in_cache(
            copy_mode="copy_context:text",
            selected_paths=view.selected_paths,
            instructions=view.instructions,
            prompt="Cached Prompt Output",
            token_count=150,
            breakdown={"files": 1},
        )

        with patch.object(QThreadPool, "start") as mock_start:
            controller._copy_context(include_xml=False, copy_destination="text")

            # QThreadPool.start không được gọi (vì cache hit)
            mock_start.assert_not_called()

            # Verify clipboard copy đúng cached prompt
            view.clipboard_service.copy_to_clipboard.assert_called_once_with(
                "Cached Prompt Output"
            )
            assert len(view.copy_breakdowns) == 1
            assert view.copy_breakdowns[0][0] == 150


def test_copy_action_generation_guard(qtbot):
    """Test cơ chế Generation Guard: hủy bỏ / bỏ qua stale workers."""
    view = MockCopyActionView()
    controller = CopyActionController(view)

    view.selected_paths = {"/mock/workspace/file1.py"}

    # Gắn file Python tồn tại
    with (
        patch("pathlib.Path.is_file", return_value=True),
        patch.object(DomainRegistry, "settings") as mock_settings,
    ):
        # Thiết lập setting
        mock_settings.return_value.enable_security_check = False

        # 1. Trình tự thành công
        # Thiết lập mock prompt generator fn
        dummy_prompt_fn = MagicMock(return_value=("Generated Prompt", 100, {}))

        # Gọi copy
        with patch.object(controller, "_do_copy_context") as mock_do:
            controller._copy_context(include_xml=False, copy_destination="text")
            mock_do.assert_called_once()

        # 2. Test _do_copy_context khởi chạy worker background
        with patch(
            "presentation.views.context.copy_action_controller.CopyTaskWorker"
        ) as mock_worker_cls:
            mock_worker = MagicMock()
            mock_worker_cls.return_value = mock_worker

            controller._do_copy_context(
                gen=1,
                workspace=view.workspace,
                file_paths=[Path("/mock/workspace/file1.py")],
                instructions=view.instructions,
                include_xml=False,
                copy_destination="text",
            )

            # Verify worker được tạo và queue vào ThreadPool
            mock_worker_cls.assert_called_once()


def test_copy_action_security_check(qtbot):
    """Test luồng Security check trước khi copy."""
    view = MockCopyActionView()
    controller = CopyActionController(view)

    view.selected_paths = {"/mock/workspace/file1.py"}

    # Bật security check
    DomainRegistry.settings().enable_security_check = True

    # Mock security scanner
    mock_scanner = MagicMock()
    DomainRegistry.register_security_scanner(mock_scanner)

    with (
        patch("pathlib.Path.is_file", return_value=True),
        patch.object(controller, "_run_security_check_then_copy") as mock_run_sec,
    ):
        controller._copy_context(include_xml=False, copy_destination="text")
        mock_run_sec.assert_called_once()


def test_copy_action_on_copy_requested_routing(qtbot):
    """Test phân luồng copy theo chế độ config (smart, full, tree-map)."""
    view = MockCopyActionView()
    controller = CopyActionController(view)

    # 1. tree_map_only
    view.copy_config.tree_map_only = True
    with patch.object(controller, "_copy_tree_map_only") as mock_tree:
        controller.on_copy_requested()
        mock_tree.assert_called_once()

    # 2. smart context
    view.copy_config.tree_map_only = False
    from domain.prompt.copy_mode import CopyMode

    view.copy_config.mode = CopyMode.SMART
    with patch.object(controller, "_copy_smart_context") as mock_smart:
        controller.on_copy_requested()
        mock_smart.assert_called_once()

    # 3. xml apply
    view.copy_config.mode = CopyMode.APPLY
    with patch.object(controller, "_copy_context") as mock_context:
        controller.on_copy_requested()
        mock_context.assert_called_once_with(include_xml=True, copy_destination="text")


def test_copy_action_warning_xml_smart_conflict(qtbot):
    """Test cảnh báo conflict khi copy XML (OPX) cùng Smart Mode."""
    view = MockCopyActionView()
    controller = CopyActionController(view)

    view.smart_mode_active = True  # Bật Smart Mode

    with patch.object(QMessageBox, "warning") as mock_warning:
        controller.on_copy_context_requested(include_xml=True)
        # Phải hiện cảnh báo không tương thích
        mock_warning.assert_called_once()
