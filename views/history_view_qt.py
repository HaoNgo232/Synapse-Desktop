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
  from views.history_view_qt import HistoryViewQt  (van hoat dong)
"""

# Re-export tat ca public symbols tu package moi
from views.history._widgets import (
    create_status_dot_icon,
    create_search_icon,
    format_date_group,
    group_entries_by_date,
    DateGroupHeader,
    OperationBadge,
    FileChangeRow,
    ErrorCard,
)
from views.history._view import HistoryViewQt

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
]
