"""
Qt Utilities - Thread-safe UI update functions cho PySide6

Sử dụng signal/slot pattern và QTimer cho UI-safe operations.
"""

from PySide6.QtCore import (
    QObject, Signal, Slot, QTimer, Qt, QRunnable, QThreadPool,
)
from typing import Callable, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SignalBridge(QObject):
    """
    Bridge để emit signals từ background threads tới main thread.
    
    Dùng signal/slot mechanism của Qt - thread-safe by design.
    
    Usage:
        bridge = SignalBridge()
        bridge.callback_signal.connect(lambda fn: fn())
        
        # Từ background thread:
        bridge.run_on_main(lambda: label.setText("Done"))
    """
    
    callback_signal = Signal(object)  # Emit callable object
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.callback_signal.connect(self._execute_callback, Qt.ConnectionType.QueuedConnection)
    
    @Slot(object)
    def _execute_callback(self, callback: Callable[[], Any]) -> None:
        """Execute callback trên main thread."""
        try:
            callback()
        except Exception as e:
            logger.error(f"Error in main-thread callback: {e}")
    
    def run_on_main(self, callback: Callable[[], Any]) -> None:
        """
        Schedule callback để chạy trên main (GUI) thread.
        
        Thread-safe: có thể gọi từ bất kỳ thread nào.
        Callback sẽ được queued và execute trên main thread.
        
        Args:
            callback: Function không nhận argument
        """
        self.callback_signal.emit(callback)


# Global signal bridge instance
_global_bridge: Optional[SignalBridge] = None


def get_signal_bridge() -> SignalBridge:
    """
    Lấy global SignalBridge instance.
    
    Tạo mới nếu chưa có. Instance này tồn tại suốt app lifetime.
    """
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = SignalBridge()
    return _global_bridge


def run_on_main_thread(callback: Callable[[], Any]) -> None:
    """
    Chạy callback trên main thread.
    Thread-safe: có thể gọi từ bất kỳ thread nào.
    
    Args:
        callback: Function sẽ được execute trên main thread
    """
    get_signal_bridge().run_on_main(callback)


class DebouncedTimer:
    """
    Debounced timer sử dụng QTimer.
    Khi start() được gọi nhiều lần, chỉ callback cuối cùng
    được execute sau khi hết delay.
    
    Usage:
        timer = DebouncedTimer(250, self._do_search)
        timer.start()  # Reset timer mỗi lần gọi
        timer.stop()   # Hủy timer
    """
    
    def __init__(
        self,
        interval_ms: int,
        callback: Callable[[], None],
        parent: Optional[QObject] = None,
    ):
        """
        Args:
            interval_ms: Delay tính bằng milliseconds
            callback: Function sẽ được gọi sau delay
            parent: QObject parent (cho memory management)
        """
        self._timer = QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(callback)
    
    def start(self, interval_ms: Optional[int] = None) -> None:
        """
        Start/restart timer. Nếu timer đang chạy sẽ bị reset.
        
        Args:
            interval_ms: Override interval (optional)
        """
        if interval_ms is not None:
            self._timer.setInterval(interval_ms)
        self._timer.start()
    
    def stop(self) -> None:
        """Cancel timer."""
        self._timer.stop()
    
    def is_active(self) -> bool:
        """Check xem timer có đang chạy không."""
        return self._timer.isActive()
    
    @property
    def interval(self) -> int:
        """Lấy interval hiện tại (ms)."""
        return self._timer.interval()
    
    @interval.setter
    def interval(self, ms: int) -> None:
        """Set interval mới (ms)."""
        self._timer.setInterval(ms)


class WorkerSignals(QObject):
    """
    Signals cho QRunnable workers.
    
    Dùng để giao tiếp kết quả từ background thread về main thread.
    """
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int, int)  # current, total


class BackgroundWorker(QRunnable):
    """
    Generic background worker sử dụng QThreadPool.
    
    Usage:
        def heavy_work():
            return compute_something()
        
        worker = BackgroundWorker(heavy_work)
        worker.signals.result.connect(self._on_result)
        worker.signals.error.connect(self._on_error)
        QThreadPool.globalInstance().start(worker)
    """
    
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)
    
    @Slot()
    def run(self) -> None:
        """Execute worker function."""
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            logger.error(f"BackgroundWorker error: {e}")
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


def schedule_background(
    fn: Callable[..., Any],
    on_result: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    on_finished: Optional[Callable[[], None]] = None,
    *args: Any,
    **kwargs: Any,
) -> BackgroundWorker:
    """
    Schedule một function chạy trên background thread.
    
    Convenience wrapper cho BackgroundWorker + QThreadPool.
    
    Args:
        fn: Function sẽ được chạy trên background thread
        on_result: Callback khi có kết quả (main thread)
        on_error: Callback khi có lỗi (main thread)
        on_finished: Callback khi hoàn tất (main thread)
        *args, **kwargs: Arguments cho fn
    
    Returns:
        BackgroundWorker instance
    """
    worker = BackgroundWorker(fn, *args, **kwargs)
    
    if on_result:
        worker.signals.result.connect(on_result)
    if on_error:
        worker.signals.error.connect(on_error)
    if on_finished:
        worker.signals.finished.connect(on_finished)
    
    QThreadPool.globalInstance().start(worker)
    return worker
