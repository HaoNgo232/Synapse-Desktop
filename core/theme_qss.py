"""
Theme QSS Generator - Tạo Qt Stylesheet từ ThemeColors

Chuyển đổi hệ thống theme từ Flet sang PySide6 QSS.
Giữ nguyên tất cả color constants từ core/theme.py.
"""

from core.theme import ThemeColors, ThemeSpacing, ThemeRadius


def generate_app_stylesheet() -> str:
    """
    Tạo global QSS stylesheet cho toàn bộ application.
    
    Áp dụng Dark Mode OLED theme với các color constants
    từ ThemeColors class.
    
    Returns:
        QSS stylesheet string
    """
    return f"""
    /* ===== GLOBAL ===== */
    QMainWindow, QWidget {{
        background-color: {ThemeColors.BG_PAGE};
        color: {ThemeColors.TEXT_PRIMARY};
        font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
        font-size: 13px;
    }}

    /* ===== LABELS ===== */
    QLabel {{
        color: {ThemeColors.TEXT_PRIMARY};
        background: transparent;
    }}
    QLabel[class="muted"] {{
        color: {ThemeColors.TEXT_MUTED};
    }}
    QLabel[class="secondary"] {{
        color: {ThemeColors.TEXT_SECONDARY};
    }}
    QLabel[class="heading"] {{
        font-size: 16px;
        font-weight: 600;
    }}
    QLabel[class="title"] {{
        font-size: 20px;
        font-weight: 600;
    }}

    /* ===== FRAMES / PANELS ===== */
    QFrame {{
        background-color: transparent;
        border: none;
    }}
    QFrame[class="surface"] {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
    }}
    QFrame[class="elevated"] {{
        background-color: {ThemeColors.BG_ELEVATED};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
    }}
    QFrame[class="card"] {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        padding: {ThemeSpacing.MD}px;
    }}

    /* ===== SEPARATORS ===== */
    QFrame[frameShape="4"] /* HLine */ {{
        background-color: {ThemeColors.BORDER};
        max-height: 1px;
        border: none;
    }}
    QFrame[frameShape="5"] /* VLine */ {{
        background-color: {ThemeColors.BORDER};
        max-width: 1px;
        border: none;
    }}

    /* ===== TAB WIDGET ===== */
    QTabWidget::pane {{
        background-color: {ThemeColors.BG_PAGE};
        border: none;
        border-top: 1px solid {ThemeColors.BORDER};
    }}
    QTabBar {{
        background-color: {ThemeColors.BG_SURFACE};
    }}
    QTabBar::tab {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_SECONDARY};
        padding: 10px 20px;
        border: none;
        border-bottom: 2px solid transparent;
        font-weight: 500;
        min-width: 80px;
    }}
    QTabBar::tab:selected {{
        color: {ThemeColors.PRIMARY};
        border-bottom: 2px solid {ThemeColors.PRIMARY};
        background-color: {ThemeColors.BG_PAGE};
    }}
    QTabBar::tab:hover {{
        color: {ThemeColors.TEXT_PRIMARY};
        background-color: {ThemeColors.BG_ELEVATED};
    }}

    /* ===== BUTTONS ===== */
    QPushButton {{
        background-color: {ThemeColors.BG_ELEVATED};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.MD}px;
        padding: 6px 16px;
        font-weight: 500;
        min-height: 28px;
    }}
    QPushButton:hover {{
        background-color: {ThemeColors.BG_HOVER};
        border-color: {ThemeColors.BORDER_LIGHT};
    }}
    QPushButton:pressed {{
        background-color: {ThemeColors.BORDER};
    }}
    QPushButton:disabled {{
        color: {ThemeColors.TEXT_MUTED};
        background-color: {ThemeColors.BG_SURFACE};
        border-color: {ThemeColors.BORDER};
    }}
    QPushButton[class="primary"] {{
        background-color: {ThemeColors.PRIMARY};
        color: #FFFFFF;
        border: none;
    }}
    QPushButton[class="primary"]:hover {{
        background-color: {ThemeColors.PRIMARY_HOVER};
    }}
    QPushButton[class="primary"]:pressed {{
        background-color: #1D4ED8;
    }}
    QPushButton[class="outlined"] {{
        background-color: transparent;
        color: {ThemeColors.TEXT_SECONDARY};
        border: 1px solid {ThemeColors.BORDER};
    }}
    QPushButton[class="outlined"]:hover {{
        background-color: {ThemeColors.BG_ELEVATED};
        color: {ThemeColors.TEXT_PRIMARY};
    }}
    QPushButton[class="flat"] {{
        background-color: transparent;
        color: {ThemeColors.TEXT_SECONDARY};
        border: none;
    }}
    QPushButton[class="flat"]:hover {{
        color: {ThemeColors.TEXT_PRIMARY};
        background-color: {ThemeColors.BG_ELEVATED};
    }}
    QPushButton[class="danger"] {{
        color: {ThemeColors.ERROR};
        border-color: {ThemeColors.ERROR};
        background-color: transparent;
    }}
    QPushButton[class="danger"]:hover {{
        background-color: #450A0A;
    }}

    QToolButton {{
        background-color: transparent;
        color: {ThemeColors.TEXT_SECONDARY};
        border: none;
        border-radius: {ThemeRadius.SM}px;
        padding: 4px;
    }}
    QToolButton:hover {{
        background-color: {ThemeColors.BG_ELEVATED};
        color: {ThemeColors.TEXT_PRIMARY};
    }}

    /* ===== TEXT INPUTS ===== */
    QLineEdit {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.MD}px;
        padding: 6px 10px;
        selection-background-color: {ThemeColors.PRIMARY};
    }}
    QLineEdit:focus {{
        border-color: {ThemeColors.PRIMARY};
    }}
    QLineEdit::placeholder {{
        color: {ThemeColors.TEXT_MUTED};
    }}
    QTextEdit, QPlainTextEdit {{
        background-color: {ThemeColors.BG_PAGE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.MD}px;
        padding: 8px;
        selection-background-color: {ThemeColors.PRIMARY};
        font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", "Consolas", monospace;
        font-size: 13px;
    }}
    QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {ThemeColors.PRIMARY};
    }}

    /* ===== COMBOBOX ===== */
    QComboBox {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.MD}px;
        padding: 4px 28px 4px 10px;
        min-height: 28px;
    }}
    QComboBox:focus {{
        border-color: {ThemeColors.PRIMARY};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {ThemeColors.TEXT_SECONDARY};
        margin-right: 8px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        selection-background-color: {ThemeColors.PRIMARY};
        selection-color: #FFFFFF;
        outline: 0;
    }}

    /* ===== CHECKBOX ===== */
    QCheckBox {{
        color: {ThemeColors.TEXT_PRIMARY};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 1px solid {ThemeColors.BORDER_LIGHT};
        background-color: transparent;
    }}
    QCheckBox::indicator:checked {{
        background-color: {ThemeColors.PRIMARY};
        border-color: {ThemeColors.PRIMARY};
    }}
    QCheckBox::indicator:hover {{
        border-color: {ThemeColors.PRIMARY};
    }}

    /* ===== PROGRESS BAR ===== */
    QProgressBar {{
        background-color: {ThemeColors.BG_SURFACE};
        border: none;
        border-radius: 5px;
        min-height: 10px;
        max-height: 10px;
        text-align: center;
        color: transparent; /* Hide text */
    }}
    QProgressBar::chunk {{
        background-color: {ThemeColors.PRIMARY};
        border-radius: 5px;
    }}

    /* ===== SCROLLBAR ===== */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {ThemeColors.BORDER};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {ThemeColors.BORDER_LIGHT};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {ThemeColors.BORDER};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {ThemeColors.BORDER_LIGHT};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    /* ===== TREE VIEW ===== */
    QTreeView {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        outline: 0;
        selection-background-color: transparent;
    }}
    QTreeView::item {{
        padding: 2px 0;
        min-height: 28px;
        background-color: transparent;
    }}
    QTreeView::item:hover {{
        background-color: transparent;
    }}
    QTreeView::item:selected {{
        background-color: transparent;
    }}
    QTreeView::branch {{
        background-color: transparent;
        border-image: none;
        image: none;
    }}
    QTreeView::branch:has-children:!has-siblings:closed,
    QTreeView::branch:closed:has-children:has-siblings {{
        border-image: none;
        image: none;
    }}
    QTreeView::branch:open:has-children:!has-siblings,
    QTreeView::branch:open:has-children:has-siblings {{
        border-image: none;
        image: none;
    }}
    QTreeView::branch:has-siblings:!adjoins-item,
    QTreeView::branch:has-siblings:adjoins-item,
    QTreeView::branch:!has-children:!has-siblings:adjoins-item {{
        border-image: none;
        image: none;
    }}

    /* ===== LIST WIDGET ===== */
    QListWidget {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        outline: 0;
    }}
    QListWidget::item {{
        padding: 6px 10px;
        border-bottom: 1px solid {ThemeColors.BORDER};
    }}
    QListWidget::item:hover {{
        background-color: {ThemeColors.BG_ELEVATED};
    }}
    QListWidget::item:selected {{
        background-color: {ThemeColors.BG_HOVER};
        color: {ThemeColors.TEXT_PRIMARY};
    }}

    /* ===== SCROLL AREA ===== */
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}

    /* ===== SPLITTER ===== */
    QSplitter::handle {{
        background-color: {ThemeColors.BORDER};
    }}
    QSplitter::handle:horizontal {{
        width: 2px;
    }}
    QSplitter::handle:vertical {{
        height: 2px;
    }}
    QSplitter::handle:hover {{
        background-color: {ThemeColors.PRIMARY};
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
        padding: 6px 24px 6px 12px;
        border-radius: {ThemeRadius.SM}px;
    }}
    QMenu::item:selected {{
        background-color: {ThemeColors.BG_ELEVATED};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {ThemeColors.BORDER};
        margin: 4px 8px;
    }}

    /* ===== DIALOG ===== */
    QDialog {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
    }}

    /* ===== TOOLTIP ===== */
    QToolTip {{
        background-color: {ThemeColors.BG_ELEVATED};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.SM}px;
        padding: 4px 8px;
        font-size: 12px;
    }}

    /* ===== GROUP BOX ===== */
    QGroupBox {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        margin-top: 12px;
        padding-top: 16px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        color: {ThemeColors.TEXT_PRIMARY};
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
    }}
    """
