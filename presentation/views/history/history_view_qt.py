"""
views/history_view_qt.py  -  REDIRECT

Module nay duoc giu lai de backward compatibility.
Logic da duoc di chuyen sang `views/history/` package:

  views/history/_widgets.py       - DateGroupHeader, OperationBadge, FileChangeRow, ErrorCard
  views/history/_list_panel.py    - HistoryListPanel (left: search + list)
  views/history/_detail_panel.py  - HistoryDetailPanel (right: detail view)
  views/history/_view.py          - HistoryViewQt (composition root)

De import HistoryViewQt:
  from views.history import HistoryViewQt  (preferred)
  from presentation.views.history.history_view_qt import HistoryViewQt  (van hoat dong)
"""

from PySide6.QtWidgets import QMessageBox
from infrastructure.adapters.clipboard_utils import copy_to_clipboard
from services.history_service import (
    get_history_entries,
    get_entry_by_id,
    clear_history,
    get_history_stats,
    delete_entry,
)
from presentation.views.history.widgets import (
    create_status_dot_icon,
    create_search_icon,
    format_date_group,
    group_entries_by_date,
    DateGroupHeader,
    OperationBadge,
    FileChangeRow,
    ErrorCard,
)
from presentation.views.history.view import HistoryViewQt

__all__ = [
    "HistoryViewQt",
    "DateGroupHeader",
    "OperationBadge",
    "FileChangeRow",
    "ErrorCard",
    "create_status_dot_icon",
    "create_search_icon",
    "format_date_group",
    "group_entries_by_date",
    "get_history_entries",
    "get_entry_by_id",
    "clear_history",
    "get_history_stats",
    "delete_entry",
    "copy_to_clipboard",
    "QMessageBox",
]
