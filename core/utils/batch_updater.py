"""
Batch Updater - Gom nhiều UI update requests thành 1 lần render

Giúp giảm giật lag khi có nhiều thay đổi UI liên tiếp.
Tương tự debounce nhưng cho page.update() calls.

Usage:
    updater = BatchUpdater(page)

    # Gọi nhiều lần, chỉ render 1 lần sau interval
    updater.request_update()
    updater.request_update()
    updater.request_update()  # -> Chỉ 1 lần update

    # Force update ngay
    updater.flush()
"""

from threading import Timer
from typing import Any, Optional


class BatchUpdater:
    """
    Gom nhiều update requests thành 1 page.update().

    Giúp UI mượt hơn khi có nhiều thay đổi liên tiếp
    (VD: chọn nhiều files nhanh).
    """

    def __init__(self, page: Any, interval_ms: int = 50):
        """
        Khởi tạo BatchUpdater.

        Args:
            page: Flet page object
            interval_ms: Thời gian batch (milliseconds)
        """
        self._page = page
        self._interval = interval_ms / 1000.0  # Convert to seconds
        self._pending = False
        self._timer: Optional[Timer] = None

    def request_update(self):
        """
        Request một UI update.

        Nếu đã có update pending, bỏ qua.
        Update sẽ được thực hiện sau interval.
        """
        if self._pending:
            return

        self._pending = True
        self._timer = Timer(self._interval, self._do_update)
        self._timer.daemon = True
        self._timer.start()

    def _do_update(self):
        """Thực hiện update sau interval."""
        self._pending = False
        try:
            if self._page:
                self._page.update()
        except Exception:
            pass  # Ignore errors (page may be closed)

    def flush(self):
        """
        Force update ngay lập tức.

        Cancel pending timer và update ngay.
        """
        if self._timer:
            self._timer.cancel()
            self._timer = None

        self._pending = False

        try:
            if self._page:
                self._page.update()
        except Exception:
            pass

    def cleanup(self):
        """Cleanup resources."""
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._pending = False
