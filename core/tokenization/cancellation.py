"""
Cancellation flag cho token counting - thread-safe.

Di chuyen tu services/token_display.py xuong core layer
de fix circular dependency (core khong duoc import tu services).

Su dung threading.Lock de dam bao thread-safe
khi doc/ghi tu nhieu threads (UI thread, worker threads).
"""

import threading

# Global cancellation state
_counting_lock = threading.Lock()
_is_counting = False


def is_counting_tokens() -> bool:
    """
    Kiem tra co dang counting tokens khong.

    Thread-safe: Su dung lock de doc gia tri.
    Goi boi batch processors de check cancellation.

    Returns:
        True neu dang counting, False neu da stop
    """
    with _counting_lock:
        return _is_counting


def start_token_counting() -> None:
    """
    Bat dau token counting - set flag = True.

    Thread-safe: Su dung lock de set gia tri.
    Goi boi TokenDisplayService.request_tokens_for_tree().
    """
    global _is_counting
    with _counting_lock:
        _is_counting = True


def stop_token_counting() -> None:
    """
    Dung token counting ngay lap tuc - set flag = False.

    Thread-safe: Su dung lock de set gia tri.
    Goi khi user switch folder, close app, hoac cancel.
    """
    global _is_counting
    with _counting_lock:
        _is_counting = False
