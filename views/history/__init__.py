"""
views/history/__init__.py

Package chua HistoryViewQt da duoc decompose.

Re-export HistoryViewQt cho backward compatibility:
    from views.history import HistoryViewQt  (moi)
    from views.history_view_qt import HistoryViewQt  (cu, van hoat dong qua redirect)
"""

from views.history._view import HistoryViewQt

__all__ = ["HistoryViewQt"]
