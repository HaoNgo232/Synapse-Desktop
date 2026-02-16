"""
SafeTimer - Thread-safe timer với cancellation và main-thread execution support.

Giải quyết các vấn đề với threading.Timer:
- Timer.cancel() không stop callback đang chạy
- Callback có thể chạy sau khi service đã cleanup
- UI updates từ Timer thread gây race condition

Usage:
    timer = SafeTimer(0.1, my_callback, page=self.page)
    timer.start()  # Start timer (auto-cancels previous)
    timer.cancel()  # Cancel timer và prevent callback
"""

import threading
from threading import Timer
from typing import Callable, Optional, Any


class SafeTimer:
    """
    Thread-safe timer với built-in cancellation và main-thread execution.

    Features:
    - Cancellation flag được check trước khi execute callback
    - Auto-cancel timer cũ khi start() được gọi lại
    - Defer UI callbacks đến main thread qua page.run_task()
    - Disposal-aware: không execute nếu đã bị disposed
    """

    def __init__(
        self,
        interval: float,
        callback: Callable[[], None],
        page: Optional[Any] = None,
        use_main_thread: bool = True,
    ):
        """
        Khởi tạo SafeTimer.

        Args:
            interval: Số giây delay trước khi execute callback
            callback: Function sẽ được gọi sau interval (không nhận arguments)
            page: Page object (legacy Flet) - nếu có và use_main_thread=True,
                  callback sẽ được defer đến main thread
            use_main_thread: Có defer callback đến main thread không
        """
        self._interval = interval
        self._callback = callback
        self._page = page
        self._use_main_thread = use_main_thread

        # Threading primitives
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self._timer: Optional[Timer] = None
        self._is_disposed = False

    def start(self):
        """
        Start timer.

        Nếu có timer đang chạy, tự động cancel trước khi start timer mới.
        Thread-safe: có thể gọi từ bất kỳ thread nào.
        """
        with self._lock:
            # Cancel timer cũ nếu có
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

            # Reset cancellation flag
            self._cancelled.clear()

            # Không start nếu đã disposed
            if self._is_disposed:
                return

            # Create và start timer mới
            self._timer = Timer(self._interval, self._execute)
            self._timer.daemon = True  # Không block app shutdown
            self._timer.start()

    def cancel(self):
        """
        Cancel timer và prevent callback execution.

        Thread-safe: có thể gọi từ bất kỳ thread nào.
        Nếu callback đang trong quá trình execute, sẽ không có effect.
        Nhưng callback sẽ check cancelled flag trước khi thực sự run.
        """
        with self._lock:
            self._cancelled.set()
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def dispose(self):
        """
        Dispose timer và prevent tất cả future callbacks.

        Gọi method này khi cleanup component/service.
        Sau khi dispose, timer không thể start lại.
        """
        with self._lock:
            self._is_disposed = True
            self._cancelled.set()
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def is_cancelled(self) -> bool:
        """Check xem timer đã bị cancel chưa."""
        return self._cancelled.is_set()

    def is_disposed(self) -> bool:
        """Check xem timer đã bị disposed chưa."""
        with self._lock:
            return self._is_disposed

    def _execute(self):
        """
        Internal method - được gọi bởi Timer thread.

        Check cancellation trước khi execute callback.
        Defer đến main thread nếu cần.
        """
        # Quick check - không cần lock vì Event là thread-safe
        if self._cancelled.is_set():
            return

        with self._lock:
            if self._is_disposed:
                return
            # Clear timer reference
            self._timer = None

        # Check lần nữa sau khi acquire lock
        if self._cancelled.is_set():
            return

        # Execute callback
        if self._use_main_thread and self._page:
            try:
                # Flet 0.80.5+ yêu cầu async function cho run_task()
                # Tạo async wrapper để wrap _safe_callback
                async def _async_callback():
                    self._safe_callback()

                # Defer đến main thread via page.run_task()
                self._page.run_task(_async_callback)
            except Exception:
                # Page không available hoặc đã closed
                pass
        else:
            # Execute trực tiếp trên Timer thread
            self._safe_callback()

    def _safe_callback(self):
        """
        Execute callback với error handling.

        Final check cancellation trước khi thực sự call.
        """
        # Final cancellation check
        if self._cancelled.is_set() or self._is_disposed:
            return

        try:
            self._callback()
        except Exception:
            # Swallow errors để không crash Timer thread
            pass


class DebouncedCallback:
    """
    Helper để debounce multiple rapid calls thành một callback duy nhất.

    Usage:
        debounced = DebouncedCallback(0.1, my_update_func, page=self.page)

        # Gọi nhiều lần liên tiếp...
        debounced.call()
        debounced.call()
        debounced.call()

        # ...chỉ execute 1 lần sau 100ms từ lần gọi cuối
    """

    def __init__(
        self,
        delay: float,
        callback: Callable[[], None],
        page: Optional[Any] = None,
    ):
        """
        Khởi tạo DebouncedCallback.

        Args:
            delay: Số giây delay sau lần gọi cuối cùng
            callback: Function sẽ được gọi (không nhận arguments)
            page: Page object (legacy Flet) cho main-thread execution
        """
        self._delay = delay
        self._callback = callback
        self._timer = SafeTimer(delay, callback, page=page, use_main_thread=True)

    def call(self):
        """
        Request callback execution.

        Mỗi lần gọi sẽ reset timer.
        Callback chỉ thực sự execute sau delay nếu không có call mới.
        """
        self._timer.start()  # Auto-cancels previous timer

    def cancel(self):
        """Cancel pending callback."""
        self._timer.cancel()

    def dispose(self):
        """Dispose và cleanup resources."""
        self._timer.dispose()
