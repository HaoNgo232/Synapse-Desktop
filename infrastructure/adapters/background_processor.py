"""
Background Processor - Web Worker style processing cho Python

Cung cấp pattern tương tự Web Workers trong JavaScript:
- Task queue với priority
- Progress callbacks
- Cancellation support
- Result callbacks trên main thread

Sử dụng ThreadPoolExecutor thay vì actual processes để:
- Share memory với main thread (cần cho Flet UI updates)
- Tránh overhead của multiprocessing
- Dễ dàng cancel tasks
"""

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Callable, Optional, Any, Dict, List, TypeVar, Generic
from enum import Enum

T = TypeVar("T")


class TaskPriority(Enum):
    """Priority levels cho tasks"""

    HIGH = 0  # UI-critical tasks
    NORMAL = 1  # Regular background tasks
    LOW = 2  # Deferred tasks


@dataclass(order=True)
class BackgroundTask:
    """
    Một task để chạy trong background.

    order=True cho phép sắp xếp theo priority.
    """

    priority: int
    task_id: str = field(compare=False)
    func: Callable[[], Any] = field(compare=False)
    on_complete: Optional[Callable[[Any], None]] = field(compare=False, default=None)
    on_error: Optional[Callable[[Exception], None]] = field(compare=False, default=None)
    on_progress: Optional[Callable[[float, str], None]] = field(
        compare=False, default=None
    )


class TaskHandle:
    """Handle để track và cancel task"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._cancelled = threading.Event()
        self._completed = threading.Event()
        self._result: Any = None
        self._error: Optional[Exception] = None

    def cancel(self):
        """Cancel task"""
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def is_completed(self) -> bool:
        return self._completed.is_set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for completion, return True if completed"""
        return self._completed.wait(timeout=timeout)

    @property
    def result(self) -> Any:
        return self._result

    @property
    def error(self) -> Optional[Exception]:
        return self._error


class BackgroundProcessor:
    """
    Background processor với task queue và worker threads.

    Tương tự Web Worker pattern:
    - submit_task(): Post message to worker
    - on_complete callback: Receive message from worker
    - cancel(): Terminate worker

    Usage:
        processor = BackgroundProcessor(workers=4)

        handle = processor.submit_task(
            task_id="count_tokens",
            func=lambda: heavy_computation(),
            on_complete=lambda result: update_ui(result),
            priority=TaskPriority.NORMAL
        )

        # Later, if needed
        handle.cancel()

        # Cleanup
        processor.shutdown()
    """

    def __init__(
        self,
        workers: int = 4,
        page=None,  # Flet page for main thread callbacks
    ):
        """
        Initialize processor.

        Args:
            workers: Số worker threads
            page: Flet Page để defer callbacks về main thread
        """
        self._workers = workers
        self._page = page
        self._executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="bg_worker"
        )

        # Task tracking
        self._tasks: Dict[str, TaskHandle] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()

        # Stats
        self._completed_count = 0
        self._cancelled_count = 0
        self._error_count = 0

        # Shutdown flag
        self._shutdown = False

    def submit_task(
        self,
        task_id: str,
        func: Callable[[], T],
        on_complete: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> TaskHandle:
        """
        Submit task to background processor.

        Args:
            task_id: Unique ID cho task
            func: Function to execute (should be thread-safe)
            on_complete: Callback khi hoàn thành (chạy trên main thread nếu có page)
            on_error: Callback khi có lỗi
            on_progress: Callback cho progress updates
            priority: Task priority

        Returns:
            TaskHandle để track/cancel task
        """
        if self._shutdown:
            raise RuntimeError("Processor đã shutdown")

        handle = TaskHandle(task_id)

        with self._lock:
            # Cancel existing task với cùng ID
            if task_id in self._tasks:
                self._tasks[task_id].cancel()

            self._tasks[task_id] = handle

        # Submit to executor
        future = self._executor.submit(
            self._execute_task,
            handle,
            func,
            on_complete,
            on_error,
        )

        with self._lock:
            self._futures[task_id] = future

        return handle

    def _execute_task(
        self,
        handle: TaskHandle,
        func: Callable[[], Any],
        on_complete: Optional[Callable[[Any], None]],
        on_error: Optional[Callable[[Exception], None]],
    ):
        """Execute task trong worker thread"""
        try:
            # Check cancellation before starting
            if handle.is_cancelled():
                self._cancelled_count += 1
                return

            # Execute function
            result = func()

            # Check cancellation after completion
            if handle.is_cancelled():
                self._cancelled_count += 1
                return

            # Store result
            handle._result = result
            handle._completed.set()
            self._completed_count += 1

            # Call completion callback
            if on_complete:
                self._invoke_callback(on_complete, result)

        except Exception as e:
            handle._error = e
            handle._completed.set()
            self._error_count += 1

            if on_error:
                self._invoke_callback(on_error, e)
        finally:
            # Cleanup
            with self._lock:
                self._tasks.pop(handle.task_id, None)
                self._futures.pop(handle.task_id, None)

    def _invoke_callback(self, callback: Callable, arg: Any):
        """
        Invoke callback, defer to main thread nếu có page.

        Flet yêu cầu UI updates phải từ main thread.
        page.run_task() sẽ schedule callback trên main thread.
        """
        if self._page:
            try:

                async def _async_callback():
                    callback(arg)

                self._page.run_task(_async_callback)
            except Exception:
                # Fallback: call directly
                callback(arg)
        else:
            callback(arg)

    def cancel_task(self, task_id: str):
        """Cancel task by ID"""
        with self._lock:
            handle = self._tasks.get(task_id)
            if handle:
                handle.cancel()

            future = self._futures.get(task_id)
            if future:
                future.cancel()

    def cancel_all(self):
        """Cancel all pending tasks"""
        with self._lock:
            for handle in self._tasks.values():
                handle.cancel()
            for future in self._futures.values():
                future.cancel()

    def get_stats(self) -> Dict[str, int]:
        """Get processing stats"""
        with self._lock:
            return {
                "pending": len(self._tasks),
                "completed": self._completed_count,
                "cancelled": self._cancelled_count,
                "errors": self._error_count,
            }

    def shutdown(self, wait: bool = False):
        """Shutdown processor"""
        self._shutdown = True
        self.cancel_all()

        try:
            self._executor.shutdown(wait=wait, cancel_futures=True)
        except TypeError:
            # Python < 3.9
            self._executor.shutdown(wait=wait)


# ============================================================================
# Batch Processing Utilities
# ============================================================================


class BatchProcessor(Generic[T]):
    """
    Process items in batches với progress tracking.

    Tương tự Array.prototype.map() với chunking.

    Usage:
        processor = BatchProcessor(items, batch_size=50)

        results = await processor.process(
            func=count_tokens,
            on_progress=lambda p: print(f"{p*100:.0f}%")
        )
    """

    def __init__(
        self,
        items: List[Any],
        batch_size: int = 50,
        executor: Optional[BackgroundProcessor] = None,
    ):
        self.items = items
        self.batch_size = batch_size
        self._executor = executor
        self._cancelled = threading.Event()

    def process_sync(
        self,
        func: Callable[[Any], T],
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> List[T]:
        """
        Process items synchronously với progress.

        Không dùng threading, nhưng yield control mỗi batch
        để cho phép cancellation.
        """
        results: List[T] = []
        total = len(self.items)

        for i in range(0, total, self.batch_size):
            if self._cancelled.is_set():
                break

            batch = self.items[i : i + self.batch_size]

            for item in batch:
                if self._cancelled.is_set():
                    break
                results.append(func(item))

            # Report progress
            if on_progress:
                progress = min(1.0, (i + len(batch)) / total)
                on_progress(progress)

        return results

    def cancel(self):
        """Cancel processing"""
        self._cancelled.set()


# Singleton processor instance
_global_processor: Optional[BackgroundProcessor] = None


def get_background_processor(page=None) -> BackgroundProcessor:
    """Get global background processor"""
    global _global_processor

    if _global_processor is None:
        _global_processor = BackgroundProcessor(workers=4, page=page)
    elif page and _global_processor._page is None:
        _global_processor._page = page

    return _global_processor


def shutdown_background_processor():
    """Shutdown global processor"""
    global _global_processor

    if _global_processor:
        _global_processor.shutdown(wait=False)
        _global_processor = None
