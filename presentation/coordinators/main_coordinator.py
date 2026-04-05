from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from PySide6.QtCore import QObject, Signal, QTimer

if TYPE_CHECKING:
    from infrastructure.di.service_container import ServiceContainer
    from presentation.main_window import SynapseMainWindow
    from shared.types.memory import MemoryStats

from infrastructure.persistence.recent_folders import (
    load_recent_folders,
    add_recent_folder,
)
from infrastructure.persistence.session_state import (
    save_session_state,
    load_session_state,
    SessionState,
)

logger = logging.getLogger(__name__)


class MainCoordinator(QObject):
    """
    Điều phối luồng công việc chính của ứng dụng.
    Tách biệt logic nghiệp vụ UI khỏi MainWindow.
    """

    workspace_changed = Signal(Path)

    def __init__(self, window: SynapseMainWindow, services: ServiceContainer):
        super().__init__(window)
        self._window = window
        self._services = services
        self._workspace_path: Optional[Path] = None

        # Git polling
        self._git_timer = QTimer(self)
        self._git_timer.setInterval(5000)  # 5s check git
        self._git_timer.timeout.connect(self._refresh_git_status)

    def start(self):
        """Khởi động coordinator."""
        self._restore_session()
        self._git_timer.start()

    @property
    def workspace_path(self) -> Optional[Path]:
        return self._workspace_path

    def set_workspace(self, path: Path):
        """Thay đổi workspace hiện tại."""
        path = path.resolve()
        if self._workspace_path == path:
            return

        self._workspace_path = path
        add_recent_folder(str(path))

        # Cập nhật UI components thông qua signals hoặc gọi trực tiếp
        self._window.top_bar.set_workspace_path(path)
        self._window.status_bar.set_workspace(path)
        self._window.update_window_title(path)

        # Notify views
        self._window.context_view.on_workspace_changed(path)
        self.workspace_changed.emit(path)

        # Refresh UI stats (Git, tokens)
        self._refresh_git_status()
        self._window.refresh_ui_stats()

    def _refresh_git_status(self):
        """Cập nhật trạng thái git từ domain service trên background thread."""
        if not self._workspace_path:
            return

        from infrastructure.adapters.qt_utils import schedule_background

        def _detect() -> Optional[str]:
            assert self._workspace_path is not None
            return self._services.git_repo.get_current_branch(self._workspace_path)

        def _on_result(branch: object):
            if isinstance(branch, str) or branch is None:
                self._window.status_bar.set_git_branch(branch)

        schedule_background(_detect, on_result=_on_result)

    def on_memory_update(self, stats: MemoryStats):
        """Xử lý cập nhật bộ nhớ."""
        self._window.top_bar.update_memory_stats(stats)

    def clear_memory(self):
        """Thực hiện giải phóng bộ nhớ."""
        import gc

        try:
            # Clear ContextView caches
            if hasattr(self._window.context_view, "file_tree_widget"):
                self._window.context_view.file_tree_widget.clear_token_cache()

            gc.collect()
            logger.info("Memory cleared by coordinator")
            self._window.refresh_ui_stats()
        except Exception as e:
            logger.error(f"Error clearing memory: {e}")

    def _restore_session(self):
        """Khôi phục session cũ."""
        recent = load_recent_folders()
        if recent:
            path = Path(recent[0])
            if path.exists() and path.is_dir():
                self.set_workspace(path)

        session = load_session_state()
        if session and session.instructions_text:
            self._window.context_view.set_instructions_text(session.instructions_text)

        if session and session.window_width and session.window_height:
            self._window.resize(session.window_width, session.window_height)

    def save_session(self):
        """Lưu session hiện tại."""
        state = SessionState(
            workspace_path=str(self._workspace_path) if self._workspace_path else None,
            instructions_text=self._window.context_view.get_instructions_text(),
            window_width=self._window.width(),
            window_height=self._window.height(),
        )
        save_session_state(state)
