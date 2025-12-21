"""
Threading Utilities - Quản lý background threads an toàn

Giải quyết race condition trong Flet:
- Global stop event cho app shutdown
- View-aware task management
- Safe UI update từ background threads
"""

import threading
import flet as ft
from typing import Callable, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


# Global stop event - set khi app đang close
_app_stop_event = threading.Event()

# Active view tracking - chỉ update UI nếu view còn active
_active_view_id: Optional[str] = None
_view_lock = threading.Lock()


def get_app_stop_event() -> threading.Event:
    """
    Lấy global stop event.
    Background threads nên check event này định kỳ.
    """
    return _app_stop_event


def signal_app_shutdown():
    """
    Gọi khi app đang close để signal tất cả threads dừng.
    """
    _app_stop_event.set()


def is_app_stopping() -> bool:
    """Check xem app có đang shutdown không."""
    return _app_stop_event.is_set()


def reset_app_state():
    """Reset state khi app restart (mainly for testing)."""
    _app_stop_event.clear()


def set_active_view(view_id: str):
    """Set ID của view đang active."""
    global _active_view_id
    with _view_lock:
        _active_view_id = view_id


def get_active_view() -> Optional[str]:
    """Lấy ID của view đang active."""
    with _view_lock:
        return _active_view_id


def is_view_active(view_id: str) -> bool:
    """
    Check xem view có còn active không.
    Dùng để quyết định có nên update UI không.
    """
    with _view_lock:
        return _active_view_id == view_id


def safe_ui_callback(
    page: ft.Page,
    view_id: str,
    callback: Callable[[], None],
) -> None:
    """
    Chạy callback trên UI thread một cách an toàn.

    Chỉ chạy nếu:
    - App không đang shutdown
    - View còn active
    - Page còn tồn tại

    Args:
        page: Flet Page object
        view_id: ID của view đã request callback
        callback: Function sẽ được gọi trên UI thread
    """
    if is_app_stopping():
        return

    if not is_view_active(view_id):
        return

    if not page:
        return

    try:
        # Kiểm tra page có method run_thread không (Flet >= 0.21)
        if hasattr(page, "run_thread"):
            # run_thread chạy callback trên UI thread từ background
            page.run_thread(callback)
        else:
            # Fallback: gọi trực tiếp (không thread-safe nhưng có try-catch)
            callback()
    except Exception:
        pass  # Ignore errors from detached controls


@dataclass
class TaskHandle:
    """Handle để track và cancel một background task."""

    task_id: str
    view_id: str
    cancel_event: threading.Event

    def cancel(self):
        """Cancel task này."""
        self.cancel_event.set()

    def is_cancelled(self) -> bool:
        """Check xem task đã bị cancel chưa."""
        return self.cancel_event.is_set() or is_app_stopping()


class TaskManager:
    """
    Quản lý background tasks với view tracking và cancellation.

    Usage:
        manager = TaskManager()

        # Start task
        handle = manager.start_task(
            view_id="context_view",
            task_func=my_long_task,
            on_complete=on_task_done,
        )

        # Cancel khi switch view
        manager.cancel_view_tasks("context_view")

        # Shutdown khi app close
        manager.shutdown()
    """

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, TaskHandle] = {}
        self._lock = threading.Lock()
        self._task_counter = 0

    def start_task(
        self,
        view_id: str,
        task_func: Callable[[threading.Event], Any],
        on_complete: Optional[Callable[[Any], None]] = None,
    ) -> TaskHandle:
        """
        Start một background task.

        Args:
            view_id: ID của view sở hữu task
            task_func: Function nhận cancel_event và return result
            on_complete: Callback khi task hoàn thành (chạy trên worker thread)

        Returns:
            TaskHandle để track/cancel task
        """
        with self._lock:
            self._task_counter += 1
            task_id = f"{view_id}_{self._task_counter}"
            cancel_event = threading.Event()
            handle = TaskHandle(task_id, view_id, cancel_event)
            self._tasks[task_id] = handle

        def wrapped_task():
            try:
                result = task_func(cancel_event)

                # Chỉ gọi callback nếu không bị cancel và view còn active
                if not handle.is_cancelled() and is_view_active(view_id):
                    if on_complete:
                        on_complete(result)
            except Exception:
                pass
            finally:
                with self._lock:
                    self._tasks.pop(task_id, None)

        self._executor.submit(wrapped_task)
        return handle

    def cancel_task(self, task_id: str):
        """Cancel một task theo ID."""
        with self._lock:
            handle = self._tasks.get(task_id)
            if handle:
                handle.cancel()

    def cancel_view_tasks(self, view_id: str):
        """Cancel tất cả tasks của một view."""
        with self._lock:
            for handle in list(self._tasks.values()):
                if handle.view_id == view_id:
                    handle.cancel()

    def cancel_all(self):
        """Cancel tất cả tasks."""
        with self._lock:
            for handle in self._tasks.values():
                handle.cancel()

    def shutdown(self, wait: bool = False):
        """
        Shutdown executor.

        Args:
            wait: Có đợi tasks hoàn thành không
        """
        self.cancel_all()
        try:
            self._executor.shutdown(wait=wait, cancel_futures=True)
        except TypeError:
            # Python < 3.9 không có cancel_futures
            self._executor.shutdown(wait=wait)


# Global task manager
_global_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Lấy global task manager (singleton)."""
    global _global_task_manager
    if _global_task_manager is None:
        _global_task_manager = TaskManager()
    return _global_task_manager


def shutdown_all():
    """
    Shutdown tất cả resources khi app close.
    Gọi từ main.py on_close handler.
    """
    signal_app_shutdown()

    global _global_task_manager
    if _global_task_manager:
        _global_task_manager.shutdown(wait=False)
        _global_task_manager = None
