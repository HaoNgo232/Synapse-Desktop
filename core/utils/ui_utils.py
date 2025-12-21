"""
UI Utilities - Safe UI update functions cho Flet

Xử lý các vấn đề phổ biến với Flet UI:
- AssertionError khi update controls chưa attached
- Safe page update từ background threads
"""

import flet as ft
from typing import Optional


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
    except AssertionError:
        # Control chưa attached hoặc đang invalid state
        # An toàn để ignore - control sẽ update khi được attach đúng cách
        pass
    except Exception:
        # Các lỗi khác cũng nên được ignore để không crash app
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
    except AssertionError:
        pass
    except Exception:
        pass
