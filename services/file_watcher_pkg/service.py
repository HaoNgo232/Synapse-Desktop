"""
FileWatcher Service - Wiring va lifecycle management.

Class nay chi lam 1 viec: khoi tao cac dependencies
(IgnoreStrategy, EventDebouncer, WorkspaceEventHandler)
va quan ly lifecycle cua watchdog Observer.

Tat ca logic cu the (ignore, debounce, event routing) da duoc
tach ra thanh cac module rieng biet.
"""

from pathlib import Path
from typing import Any, Callable, Optional

from watchdog.observers import Observer

from core.logging_config import log_info, log_error
from services.interfaces.file_watcher_service import (
    IFileWatcherService,
    IIgnoreStrategy,
    WatcherCallbacks,
)
from services.file_watcher_pkg.debouncer import TimerEventDebouncer
from services.file_watcher_pkg.handler import WorkspaceEventHandler
from services.file_watcher_pkg.ignore_strategies import DefaultIgnoreStrategy


class FileWatcher(IFileWatcherService):
    """
    Service theo doi thay doi file trong workspace.

    Wiring dependencies:
    - IIgnoreStrategy -> DefaultIgnoreStrategy (co the thay doi qua constructor)
    - IEventDebouncer -> TimerEventDebouncer (tao moi moi lan start)
    - WorkspaceEventHandler cau noi giua watchdog va debouncer

    Features:
    - Theo doi file created/deleted/modified/moved
    - Debounce events de tranh spam
    - Auto-ignore cac thu muc nhu .git, node_modules (qua strategy)
    - Chay trong background thread

    Usage:
        watcher = FileWatcher()
        watcher.start(Path("/path/to/workspace"), on_change=lambda: refresh_tree())
        # ... later
        watcher.stop()
    """

    def __init__(
        self,
        ignore_strategy: Optional[IIgnoreStrategy] = None,
    ):
        """
        Khoi tao FileWatcher voi optional custom ignore strategy.

        Args:
            ignore_strategy: Strategy xac dinh path nao can bo qua.
                             Mac dinh su dung DefaultIgnoreStrategy.
        """
        # Su dung Any de tranh Pyrefly false positive voi Observer type
        self._observer: Optional[Any] = None
        self._debouncer: Optional[TimerEventDebouncer] = None
        self._handler: Optional[WorkspaceEventHandler] = None
        self._current_path: Optional[Path] = None
        self._ignore_strategy: IIgnoreStrategy = (
            ignore_strategy or DefaultIgnoreStrategy()
        )

    def start(
        self,
        path: Path,
        on_change: Optional[Callable[[], None]] = None,
        callbacks: Optional[WatcherCallbacks] = None,
        debounce_seconds: float = 0.5,
    ) -> None:
        """
        Bat dau theo doi mot thu muc.

        Neu dang theo doi thu muc khac, se tu dong stop truoc.

        Co the dung on_change (backward compatible) hoac callbacks (incremental).

        Args:
            path: Duong dan thu muc can theo doi
            on_change: Callback legacy khi co thay doi (backward compatible)
            callbacks: WatcherCallbacks cho incremental updates
            debounce_seconds: Thoi gian debounce (mac dinh 0.5s)
        """
        # Stop watcher cu neu co
        self.stop()

        if not path.exists() or not path.is_dir():
            log_error(f"[FileWatcher] Invalid path: {path}")
            return

        # Build callbacks - support both old and new API
        if callbacks is None:
            callbacks = WatcherCallbacks(on_batch_change=on_change)

        try:
            # Wire dependencies: Strategy -> Debouncer -> Handler -> Observer
            self._debouncer = TimerEventDebouncer(
                callbacks=callbacks,
                debounce_seconds=debounce_seconds,
            )

            self._handler = WorkspaceEventHandler(
                ignore_strategy=self._ignore_strategy,
                debouncer=self._debouncer,
            )

            self._observer = Observer()
            self._observer.schedule(
                self._handler,
                str(path),
                recursive=True,
            )
            self._observer.start()

            self._current_path = path
            log_info(f"[FileWatcher] Started watching: {path}")

        except Exception as e:
            log_error(f"[FileWatcher] Failed to start: {e}")
            self.stop()

    def stop(self) -> None:
        """Dung theo doi."""
        if self._debouncer is not None:
            self._debouncer.cleanup()
            self._debouncer = None

        self._handler = None

        observer = self._observer
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=2.0)
                log_info(f"[FileWatcher] Stopped watching: {self._current_path}")
            except Exception as e:
                log_error(f"[FileWatcher] Error stopping: {e}")
            finally:
                self._observer = None

        self._current_path = None

    def is_running(self) -> bool:
        """Kiem tra watcher co dang chay khong."""
        observer = self._observer
        return observer is not None and observer.is_alive()

    @property
    def current_path(self) -> Optional[Path]:
        """Lay duong dan dang duoc theo doi."""
        return self._current_path
