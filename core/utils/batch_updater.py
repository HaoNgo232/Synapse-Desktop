"""
Batch Updater - Gom nhiều UI update requests thành 1 lần render

Giúp giảm giật lag khi có nhiều thay đổi UI liên tiếp.
Tương tự debounce nhưng cho page.update() calls.

PERFORMANCE IMPROVEMENTS:
- Coalescing multiple updates
- Adaptive rate limiting based on update frequency
- Dirty tracking to skip unnecessary updates

Usage:
    updater = BatchUpdater(page)

    # Gọi nhiều lần, chỉ render 1 lần sau interval
    updater.request_update()
    updater.request_update()
    updater.request_update()  # -> Chỉ 1 lần update

    # Force update ngay
    updater.flush()
"""

import time
import threading
from typing import Any, Optional, Set, Callable


class BatchUpdater:
    """
    Gom nhiều update requests thành 1 page.update().

    PERFORMANCE FEATURES:
    - Adaptive interval: tăng interval khi update quá thường xuyên
    - Dirty tracking: skip update nếu không có thay đổi thực sự
    - Coalescing: gom nhiều request trong cùng frame
    """

    # Adaptive rate limiting thresholds
    MIN_INTERVAL_MS = 16  # ~60fps
    DEFAULT_INTERVAL_MS = 50
    MAX_INTERVAL_MS = 200
    
    # If more than this many updates in 1 second, increase interval
    RATE_LIMIT_THRESHOLD = 20

    def __init__(self, page: Any, interval_ms: int = DEFAULT_INTERVAL_MS):
        """
        Khởi tạo BatchUpdater.

        Args:
            page: Flet page object
            interval_ms: Thời gian batch (milliseconds)
        """
        self._page = page
        self._base_interval = interval_ms / 1000.0
        self._current_interval = self._base_interval
        self._pending = False
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        
        # Rate limiting tracking
        self._update_count = 0
        self._last_rate_check = time.time()
        
        # Dirty tracking
        self._dirty_controls: Set[int] = set()  # Track by control id
        self._last_update_time = 0.0

    def request_update(self, control_id: Optional[int] = None):
        """
        Request một UI update.

        Args:
            control_id: Optional ID của control đã thay đổi (for dirty tracking)
        """
        with self._lock:
            # Track dirty control if provided
            if control_id is not None:
                self._dirty_controls.add(control_id)
            
            if self._pending:
                return

            self._pending = True
            self._update_count += 1
            
            # Adaptive interval adjustment
            self._adjust_interval()
            
            self._timer = threading.Timer(self._current_interval, self._do_update)
            self._timer.daemon = True
            self._timer.start()

    def _adjust_interval(self):
        """Điều chỉnh interval dựa trên tần suất update."""
        now = time.time()
        elapsed = now - self._last_rate_check
        
        if elapsed >= 1.0:
            # Check rate over last second
            rate = self._update_count / elapsed
            
            if rate > self.RATE_LIMIT_THRESHOLD:
                # Too many updates, increase interval
                self._current_interval = min(
                    self._current_interval * 1.5,
                    self.MAX_INTERVAL_MS / 1000.0
                )
            elif rate < self.RATE_LIMIT_THRESHOLD / 2:
                # Low update rate, decrease interval for responsiveness
                self._current_interval = max(
                    self._current_interval * 0.8,
                    self.MIN_INTERVAL_MS / 1000.0
                )
            
            # Reset counters
            self._update_count = 0
            self._last_rate_check = now

    def _do_update(self):
        """Thực hiện update sau interval."""
        with self._lock:
            self._pending = False
            dirty_count = len(self._dirty_controls)
            self._dirty_controls.clear()
        
        try:
            if self._page:
                # Skip if no dirty controls and recent update
                now = time.time()
                if dirty_count == 0 and (now - self._last_update_time) < 0.1:
                    return
                
                self._page.update()
                self._last_update_time = now
        except Exception:
            pass  # Ignore errors (page may be closed)

    def flush(self):
        """
        Force update ngay lập tức.

        Cancel pending timer và update ngay.
        """
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            self._pending = False
            self._dirty_controls.clear()

        try:
            if self._page:
                self._page.update()
                self._last_update_time = time.time()
        except Exception:
            pass

    def cleanup(self):
        """Cleanup resources."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            self._pending = False
            self._dirty_controls.clear()


class ThrottledCallback:
    """
    Throttle callback execution to max N times per second.
    
    Unlike debounce (waits for silence), throttle ensures
    callback runs at most once per interval, even during continuous calls.
    """
    
    def __init__(
        self,
        callback: Callable[[], None],
        min_interval_ms: int = 100,
    ):
        self._callback = callback
        self._min_interval = min_interval_ms / 1000.0
        self._last_call = 0.0
        self._pending = False
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
    
    def call(self):
        """Request callback execution (throttled)."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            
            if elapsed >= self._min_interval:
                # Enough time passed, execute immediately
                self._last_call = now
                self._execute()
            elif not self._pending:
                # Schedule for later
                self._pending = True
                delay = self._min_interval - elapsed
                self._timer = threading.Timer(delay, self._delayed_execute)
                self._timer.daemon = True
                self._timer.start()
    
    def _execute(self):
        """Execute callback."""
        try:
            self._callback()
        except Exception:
            pass
    
    def _delayed_execute(self):
        """Execute after delay."""
        with self._lock:
            self._pending = False
            self._last_call = time.time()
        self._execute()
    
    def cancel(self):
        """Cancel pending callback."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            self._pending = False