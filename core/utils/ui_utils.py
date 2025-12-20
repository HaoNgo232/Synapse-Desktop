"""
UI Update Utilities

Helper functions để safely update Flet UI controls.
"""

import flet as ft
from typing import Optional


def safe_page_update(page: Optional[ft.Page]) -> None:
    """
    Safely update page, catching AssertionError if controls not attached.

    Flet raises AssertionError when trying to update controls that:
    - Haven't been added to page yet
    - Have been removed from page
    - Are in invalid state

    Args:
        page: Flet Page object to update
    """
    if not page:
        return

    try:
        page.update()
    except AssertionError:
        # Control not yet attached to page or in invalid state
        # This is safe to ignore - the control will update when properly attached
        pass
    except Exception:
        # Other errors should be logged but not crash
        pass
