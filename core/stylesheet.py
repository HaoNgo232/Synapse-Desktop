"""
Global stylesheet for Synapse Desktop
Applies design system: hover states, focus states, cursor pointer
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget
from core.theme import ThemeColors, ThemeRadius


def apply_cursor_pointer(widget: QWidget) -> None:
    """Apply pointer cursor to clickable widget."""
    widget.setCursor(Qt.CursorShape.PointingHandCursor)


def setup_button(button: QPushButton, tooltip: str = "") -> None:
    """Setup button with cursor pointer and optional tooltip."""
    apply_cursor_pointer(button)
    if tooltip:
        button.setToolTip(tooltip)


def get_global_stylesheet() -> str:
    """Get complete application stylesheet with design system."""
    return f"""
    /* ===== GLOBAL ===== */
    QWidget {{
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 12px;
    }}
    
    /* ===== BUTTONS ===== */
    QPushButton {{
        background-color: {ThemeColors.PRIMARY};
        color: white;
        border: none;
        border-radius: {ThemeRadius.LG}px;
        padding: 8px 16px;
        font-weight: 600;
        font-size: 12px;
    }}
    
    QPushButton:hover {{
        background-color: {ThemeColors.PRIMARY_HOVER};
    }}
    
    QPushButton:pressed {{
        background-color: #1E40AF;
    }}
    
    QPushButton:disabled {{
        background-color: {ThemeColors.BG_ELEVATED};
        color: {ThemeColors.TEXT_MUTED};
    }}
    
    /* Flat buttons (secondary style) */
    QPushButton[class="flat"] {{
        background-color: transparent;
        color: {ThemeColors.TEXT_SECONDARY};
        border: 1px solid {ThemeColors.BORDER};
    }}
    
    QPushButton[class="flat"]:hover {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border-color: {ThemeColors.BORDER_LIGHT};
    }}
    
    /* ===== INPUT FIELDS ===== */
    QLineEdit {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        padding: 8px 12px;
        font-size: 12px;
    }}
    
    QLineEdit:focus {{
        border: 2px solid {ThemeColors.BORDER_FOCUS};
        background-color: {ThemeColors.BG_PAGE};
        padding: 7px 11px;  /* Adjust for 2px border */
    }}
    
    QLineEdit:hover {{
        border-color: {ThemeColors.BORDER_LIGHT};
    }}
    
    /* ===== TEXT EDIT ===== */
    QTextEdit, QPlainTextEdit {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        padding: 8px;
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 12px;
    }}
    
    QTextEdit:focus, QPlainTextEdit:focus {{
        border: 2px solid {ThemeColors.BORDER_FOCUS};
    }}
    
    /* ===== TREE VIEW ===== */
    QTreeView {{
        background-color: {ThemeColors.BG_PAGE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        padding: 4px;
        outline: none;
    }}
    
    QTreeView::item {{
        padding: 6px;
        border-radius: {ThemeRadius.SM}px;
    }}
    
    QTreeView::item:hover {{
        background-color: {ThemeColors.BG_SURFACE};
    }}
    
    QTreeView::item:selected {{
        background-color: {ThemeColors.PRIMARY};
        color: white;
    }}
    
    QTreeView::branch {{
        background-color: transparent;
    }}
    
    /* ===== TAB WIDGET ===== */
    QTabWidget::pane {{
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        background-color: {ThemeColors.BG_PAGE};
        top: -1px;
    }}
    
    QTabBar::tab {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_SECONDARY};
        padding: 10px 20px;
        border-top-left-radius: {ThemeRadius.LG}px;
        border-top-right-radius: {ThemeRadius.LG}px;
        margin-right: 4px;
        font-weight: 500;
        font-size: 12px;
    }}
    
    QTabBar::tab:selected {{
        background-color: {ThemeColors.PRIMARY};
        color: white;
    }}
    
    QTabBar::tab:hover:!selected {{
        background-color: {ThemeColors.BG_ELEVATED};
        color: {ThemeColors.TEXT_PRIMARY};
    }}
    
    /* ===== COMBO BOX ===== */
    QComboBox {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        padding: 6px 12px;
        font-size: 12px;
    }}
    
    QComboBox:hover {{
        border-color: {ThemeColors.BORDER_LIGHT};
    }}
    
    QComboBox:focus {{
        border: 2px solid {ThemeColors.BORDER_FOCUS};
    }}
    
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.MD}px;
        selection-background-color: {ThemeColors.PRIMARY};
        selection-color: white;
    }}
    
    /* ===== SCROLL BAR ===== */
    QScrollBar:vertical {{
        background-color: {ThemeColors.BG_PAGE};
        width: 12px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {ThemeColors.BG_ELEVATED};
        border-radius: 6px;
        min-height: 30px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {ThemeColors.BG_HOVER};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    QScrollBar:horizontal {{
        background-color: {ThemeColors.BG_PAGE};
        height: 12px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {ThemeColors.BG_ELEVATED};
        border-radius: 6px;
        min-width: 30px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {ThemeColors.BG_HOVER};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    
    /* ===== LABELS ===== */
    QLabel {{
        color: {ThemeColors.TEXT_PRIMARY};
        font-size: 12px;
    }}
    
    QLabel[class="heading"] {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 15px;
        font-weight: bold;
        color: {ThemeColors.TEXT_PRIMARY};
    }}
    
    QLabel[class="muted"] {{
        color: {ThemeColors.TEXT_MUTED};
        font-size: 11px;
    }}
    
    /* ===== TOOLTIPS ===== */
    QToolTip {{
        background-color: {ThemeColors.BG_ELEVATED};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.MD}px;
        padding: 6px 10px;
        font-size: 10px;
    }}
    
    /* ===== MENU ===== */
    QMenu {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.MD}px;
        padding: 4px;
    }}
    
    QMenu::item {{
        padding: 6px 20px;
        border-radius: {ThemeRadius.SM}px;
    }}
    
    QMenu::item:selected {{
        background-color: {ThemeColors.PRIMARY};
        color: white;
    }}
    
    /* ===== STATUS BAR ===== */
    QStatusBar {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_SECONDARY};
        border-top: 1px solid {ThemeColors.BORDER};
        font-size: 10px;
    }}
    
    /* ===== PROGRESS BAR ===== */
    QProgressBar {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.SM}px;
        text-align: center;
        color: {ThemeColors.TEXT_PRIMARY};
        font-size: 10px;
    }}
    
    QProgressBar::chunk {{
        background-color: {ThemeColors.PRIMARY};
        border-radius: {ThemeRadius.SM}px;
    }}
    """
