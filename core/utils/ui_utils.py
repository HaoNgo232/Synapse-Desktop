"""
UI Utilities - Safe UI update functions cho Flet

Xử lý các vấn đề phổ biến với Flet UI:
- AssertionError khi update controls chưa attached
- Safe page update từ background threads
- Batched updates để giảm jank
"""

import flet as ft
import threading
import time
from typing import Optional, List, Callable
from functools import wraps


# Global update coalescing
_update_lock = threading.Lock()
_pending_pages: set = set()
_last_update_time: float = 0.0
_MIN_UPDATE_INTERVAL = 0.016  # ~60fps


def safe_page_update(page: Optional[ft.Page]) -> None:
    """
    Safely update page, catching AssertionError if controls not attached.

    Flet raises AssertionError khi cố update controls mà:
    - Chưa được add vào page
    - Đã bị remove khỏi page
    - Đang ở invalid state

    Args:
        page: Flet Page object để update
    """
    if not page:
        return

    try:
        page.update()
    except AssertionError as e:
        # Control chưa attached hoặc đang invalid state
        try:
            from core.logging_config import log_debug
            log_debug(f"UI Update Warning (AssertionError): {e}")
        except ImportError:
            pass
    except Exception as e:
        try:
            from core.logging_config import log_error
            log_error(f"UI Update Error: {e}")
        except ImportError:
            pass


def safe_control_update(control: Optional[ft.Control]) -> None:
    """
    Safely update một control cụ thể.

    Args:
        control: Flet Control object để update
    """
    if not control:
        return

    try:
        control.update()
    except AssertionError as e:
        try:
            from core.logging_config import log_debug
            log_debug(f"Control Update Warning (AssertionError): {e}")
        except ImportError:
            pass
    except Exception as e:
        try:
            from core.logging_config import log_error
            log_error(f"Control Update Error: {e}")
        except ImportError:
            pass


def coalesced_update(page: Optional[ft.Page]) -> None:
    """
    Request coalesced page update.
    
    Multiple calls within MIN_UPDATE_INTERVAL will be combined
    into a single page.update() call.
    
    Args:
        page: Flet Page object để update
    """
    global _last_update_time
    
    if not page:
        return
    
    with _update_lock:
        now = time.time()
        if now - _last_update_time >= _MIN_UPDATE_INTERVAL:
            _last_update_time = now
            safe_page_update(page)


def batch_control_updates(controls: List[ft.Control]) -> None:
    """
    Update multiple controls efficiently.
    
    Groups controls by page and performs single update per page.
    
    Args:
        controls: List of controls to update
    """
    if not controls:
        return
    
    # Group by page
    pages: set = set()
    for control in controls:
        if control and hasattr(control, 'page') and control.page:
            pages.add(control.page)
    
    # Single update per page
    for page in pages:
        safe_page_update(page)


def throttled(min_interval_ms: int = 100):
    """
    Decorator to throttle function calls.
    
    Ensures function is called at most once per min_interval_ms.
    
    Usage:
        @throttled(100)
        def update_display():
            ...
    """
    min_interval = min_interval_ms / 1000.0
    
    def decorator(func: Callable) -> Callable:
        last_call = [0.0]  # Use list for mutable closure
        lock = threading.Lock()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                now = time.time()
                if now - last_call[0] >= min_interval:
                    last_call[0] = now
                    return func(*args, **kwargs)
            return None
        
        return wrapper
    
    return decorator


def run_on_main_thread(page: ft.Page, callback: Callable[[], None]) -> None:
    """
    Run callback on main thread via page.run_task().
    
    Safely handles case where page might be None or closed.
    
    Args:
        page: Flet Page object
        callback: Sync callback to run on main thread
    """
    if not page:
        return
    
    try:
        async def _async_wrapper():
            try:
                callback()
            except Exception:
                pass
        
        page.run_task(_async_wrapper)
    except Exception:
        pass  # Page closed or unavailable