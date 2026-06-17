"""
Error Guard — Decorator để bắt và log exception âm thầm một cách có kiểm soát.

Thay thế pattern `except Exception: pass` bằng cách log ERROR + full traceback,
đồng thời giữ behavior "không crash caller" cho các hàm callback/timer.

Usage:
    from shared.error_guard import guard_errors

    @guard_errors("MyClass._on_timer")
    def _on_timer(self) -> None:
        ...  # lỗi ở đây sẽ được log thay vì nuốt âm thầm

    @guard_errors()  # dùng qualname tự động
    def my_callback() -> None:
        ...
"""

import functools
import logging
from typing import Any, Callable, TypeVar

_logger = logging.getLogger("synapse-desktop")

F = TypeVar("F", bound=Callable[..., Any])


def guard_errors(label: str | None = None) -> Callable[[F], F]:
    """
    Decorator bảo vệ hàm khỏi nuốt lỗi âm thầm.

    Khi hàm decorated raise exception:
    - Log ERROR với full traceback (exc_info=True) lên logger "synapse-desktop"
    - Trả về None thay vì propagate exception

    Args:
        label: Tên hiển thị trong log message. Nếu None, dùng fn.__qualname__.

    Returns:
        Decorator function.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception:
                name = label or fn.__qualname__
                _logger.error(
                    f"Unhandled exception in '{name}'",
                    exc_info=True,
                )
                return None

        return wrapper  # type: ignore[return-value]

    return decorator
