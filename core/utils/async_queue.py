"""
Async Task Queue - Concurrency control cho async operations

Tương tự p-queue trong JavaScript/Node.js (PasteMax).
Chạy trong single event loop nên KHÔNG có race condition.

Features:
- Concurrency limit với semaphore
- Global cancellation flag
- Graceful cleanup
"""

import asyncio
from typing import Any, Callable, Coroutine, Optional, List, TypeVar
from dataclasses import dataclass

T = TypeVar("T")


@dataclass
class QueueStats:
    """Thống kê queue"""

    pending: int = 0
    running: int = 0
    completed: int = 0
    cancelled: int = 0


class AsyncTaskQueue:
    """
    Async task queue với concurrency control.

    Tương tự p-queue trong JavaScript - giới hạn số tasks
    chạy đồng thời mà không tạo threads thực sự.

    Usage:
        queue = AsyncTaskQueue(concurrency=4)

        # Add tasks
        result = await queue.add(my_async_function())

        # Or add many
        results = await queue.add_many([
            async_func1(),
            async_func2(),
        ])

        # Cancel tất cả
        queue.cancel_all()

        # Wait for idle
        await queue.wait_idle()
    """

    def __init__(self, concurrency: int = 4):
        """
        Khởi tạo queue.

        Args:
            concurrency: Số tasks tối đa chạy đồng thời
        """
        self._concurrency = max(1, concurrency)
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._cancelled = False
        self._tasks: List[asyncio.Task] = []

        # Stats
        self._pending = 0
        self._running = 0
        self._completed = 0

    @property
    def is_cancelled(self) -> bool:
        """Check xem queue đã bị cancel chưa"""
        return self._cancelled

    @property
    def stats(self) -> QueueStats:
        """Lấy thống kê queue"""
        return QueueStats(
            pending=self._pending,
            running=self._running,
            completed=self._completed,
            cancelled=1 if self._cancelled else 0,
        )

    async def add(
        self,
        coro: Coroutine[Any, Any, T],
        check_cancelled: bool = True,
    ) -> Optional[T]:
        """
        Add một coroutine vào queue.

        Args:
            coro: Coroutine cần chạy
            check_cancelled: Có check cancellation flag không

        Returns:
            Kết quả của coroutine hoặc None nếu bị cancel
        """
        if check_cancelled and self._cancelled:
            # Close coroutine để tránh warning
            coro.close()
            return None

        self._pending += 1

        try:
            async with self._semaphore:
                self._pending -= 1
                self._running += 1

                if check_cancelled and self._cancelled:
                    return None

                try:
                    result = await coro
                    self._completed += 1
                    return result
                except asyncio.CancelledError:
                    return None
                finally:
                    self._running -= 1
        except Exception:
            self._pending = max(0, self._pending - 1)
            raise

    async def add_many(
        self,
        coros: List[Coroutine[Any, Any, T]],
    ) -> List[Any]:
        """
        Add nhiều coroutines và đợi tất cả hoàn thành.

        Args:
            coros: List các coroutines

        Returns:
            List kết quả (có thể chứa None nếu bị cancel)
        """
        tasks = [asyncio.create_task(self.add(coro)) for coro in coros]
        self._tasks.extend(tasks)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Clean up completed tasks
        for task in tasks:
            if task in self._tasks:
                self._tasks.remove(task)

        # Convert exceptions to None
        return [r if not isinstance(r, Exception) else None for r in results]

    def cancel_all(self):
        """
        Cancel tất cả pending và running tasks.

        Set flag để tasks mới không được accept,
        và cancel các tasks đang chạy.
        """
        self._cancelled = True

        for task in self._tasks:
            if not task.done():
                task.cancel()

        self._tasks.clear()

    def reset(self):
        """
        Reset queue để sử dụng lại.

        Clear cancellation flag và stats.
        """
        self._cancelled = False
        self._pending = 0
        self._running = 0
        self._completed = 0
        self._tasks.clear()

    async def wait_idle(self, timeout: Optional[float] = None):
        """
        Đợi cho đến khi queue idle (không có tasks nào đang chạy).

        Args:
            timeout: Timeout in seconds (None = no timeout)
        """

        async def wait_for_idle():
            while self._running > 0 or self._pending > 0:
                await asyncio.sleep(0.01)

        if timeout:
            await asyncio.wait_for(wait_for_idle(), timeout=timeout)
        else:
            await wait_for_idle()


# Global cancellation flag cho file processing
# Giống isLoadingDirectory trong PasteMax
_is_processing = False


def is_processing() -> bool:
    """Check xem có đang processing không"""
    return _is_processing


def start_processing():
    """Bắt đầu processing session"""
    global _is_processing
    _is_processing = True


def stop_processing():
    """Dừng processing session"""
    global _is_processing
    _is_processing = False


async def run_with_cancellation(
    coro: Coroutine[Any, Any, T],
    check_interval: float = 0.1,
) -> Optional[T]:
    """
    Chạy coroutine với periodic cancellation check.

    Args:
        coro: Coroutine cần chạy
        check_interval: Interval để check cancellation (seconds)

    Returns:
        Kết quả hoặc None nếu bị cancel
    """
    if not _is_processing:
        coro.close()
        return None

    task = asyncio.create_task(coro)

    while not task.done():
        if not _is_processing:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return None

        await asyncio.sleep(check_interval)

    return task.result()
