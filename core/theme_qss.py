"""
Theme QSS Generator — Synapse Desktop Design System

Generates a comprehensive Qt stylesheet from ThemeColors / ThemeSpacing / ThemeRadius.
Inspired by VS Code & JetBrains dark themes: subtle borders, clear hierarchy,
smooth hover transitions, thin scrollbars, and clean typography.
"""

import os

from core.theme import ThemeColors, ThemeSpacing, ThemeRadius, ThemeFonts

# Resolve absolute paths for SVG icons used in tree-view branch indicators
_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
)
_ARROW_RIGHT = os.path.join(_ASSETS_DIR, "arrow-right.svg").replace("\\", "/")
_ARROW_DOWN = os.path.join(_ASSETS_DIR, "arrow-down.svg").replace("\\", "/")


def generate_app_stylesheet() -> str:
    """
    Generate the global QSS stylesheet for the entire application.

    Returns:
        Complete QSS string ready to apply via QApplication.setStyleSheet().
    """
    return f"""
    /* ================================================================
       GLOBAL — base font, background, text color
       ================================================================ */
    QMainWindow, QWidget {{
        background-color: {ThemeColors.BG_PAGE};
        color: {ThemeColors.TEXT_PRIMARY};
        font-family: {ThemeFonts.FAMILY_BODY};
        font-size: {ThemeFonts.SIZE_BODY}px;
    }}

    /* ================================================================
       LABELS
       ================================================================ */
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
        font-size: {ThemeFonts.SIZE_TITLE}px;
        font-weight: 600;
    }}
    QLabel[class="title"] {{
        font-size: {ThemeFonts.SIZE_HEADING}px;
        font-weight: 700;
    }}

    /* ================================================================
       FRAMES / PANELS
       ================================================================ */
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

    /* ================================================================
       SEPARATORS
       ================================================================ */
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

    /* ================================================================
       TAB WIDGET — Bottom-border accent style (VS Code look)
       ================================================================ */
    QTabWidget::pane {{
        background-color: {ThemeColors.BG_PAGE};
        border: none;
        border-top: 1px solid {ThemeColors.BORDER};
    }}
    QTabBar {{
        background-color: {ThemeColors.BG_SURFACE};
        qproperty-drawBase: 0;
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {ThemeColors.TAB_INACTIVE_TEXT};
        padding: 10px 24px;
        border: none;
        border-bottom: 3px solid transparent;
        font-weight: 500;
        font-size: {ThemeFonts.SIZE_BODY}px;
        min-width: 90px;
    }}
    QTabBar::tab:selected {{
        color: {ThemeColors.TEXT_PRIMARY};
        border-bottom: 3px solid {ThemeColors.TAB_ACTIVE_BORDER};
        background-color: {ThemeColors.TAB_ACTIVE_BG};
        font-weight: 700;
    }}
    QTabBar::tab:hover:!selected {{
        color: {ThemeColors.TEXT_PRIMARY};
        background-color: rgba(124, 111, 255, 0.08);
    }}

    /* ================================================================
       BUTTONS — Default is secondary/outlined
       ================================================================ */
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
    QPushButton:focus {{
        border-color: {ThemeColors.BORDER_FOCUS};
    }}

    /* Primary — accent background, white text */
    QPushButton[class="primary"] {{
        background-color: {ThemeColors.PRIMARY};
        color: #FFFFFF;
        border: none;
    }}
    QPushButton[class="primary"]:hover {{
        background-color: {ThemeColors.PRIMARY_HOVER};
    }}
    QPushButton[class="primary"]:pressed {{
        background-color: {ThemeColors.PRIMARY_PRESSED};
    }}

    /* Outlined — transparent bg, visible border */
    QPushButton[class="outlined"] {{
        background-color: transparent;
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER_LIGHT};
    }}
    QPushButton[class="outlined"]:hover {{
        background-color: {ThemeColors.BG_ELEVATED};
        border-color: {ThemeColors.PRIMARY};
    }}
    QPushButton[class="outlined"]:pressed {{
        background-color: {ThemeColors.BG_HOVER};
    }}

    /* Flat / Ghost — no border, subtle hover */
    QPushButton[class="flat"] {{
        background-color: transparent;
        color: {ThemeColors.TEXT_SECONDARY};
        border: none;
    }}
    QPushButton[class="flat"]:hover {{
        color: {ThemeColors.TEXT_PRIMARY};
        background-color: {ThemeColors.BG_ELEVATED};
    }}

    /* Danger — red background */
    QPushButton[class="danger"] {{
        background-color: {ThemeColors.ERROR_BG};
        color: #FFFFFF;
        border: none;
    }}
    QPushButton[class="danger"]:hover {{
        background-color: {ThemeColors.ERROR_BG_HOVER};
    }}
    QPushButton[class="danger"]:pressed {{
        background-color: #991B1B;
    }}

    /* Success — green background */
    QPushButton[class="success"] {{
        background-color: {ThemeColors.SUCCESS_BG};
        color: #FFFFFF;
        border: none;
    }}
    QPushButton[class="success"]:hover {{
        background-color: {ThemeColors.SUCCESS_BG_HOVER};
    }}

    /* Warning — amber background */
    QPushButton[class="warning"] {{
        background-color: {ThemeColors.WARNING_BG};
        color: #FFFFFF;
        border: none;
    }}
    QPushButton[class="warning"]:hover {{
        background-color: {ThemeColors.WARNING_BG_HOVER};
    }}

    /* ================================================================
       TOOL BUTTONS
       ================================================================ */
    QToolButton {{
        background-color: transparent;
        color: {ThemeColors.TEXT_SECONDARY};
        border: none;
        border-radius: {ThemeRadius.MD}px;
        padding: 6px;
    }}
    QToolButton:hover {{
        background-color: {ThemeColors.BG_ELEVATED};
        color: {ThemeColors.TEXT_PRIMARY};
    }}

    /* ================================================================
       TEXT INPUTS
       ================================================================ */
    QLineEdit {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.MD}px;
        padding: 6px 12px;
        selection-background-color: {ThemeColors.PRIMARY};
    }}
    QLineEdit:focus {{
        border-color: {ThemeColors.BORDER_FOCUS};
    }}
    QLineEdit:hover {{
        border-color: {ThemeColors.BORDER_LIGHT};
    }}
    QLineEdit::placeholder {{
        color: {ThemeColors.TEXT_MUTED};
    }}

    QTextEdit, QPlainTextEdit {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.LG}px;
        padding: {ThemeSpacing.SM}px;
        selection-background-color: {ThemeColors.PRIMARY};
        font-family: {ThemeFonts.FAMILY_MONO};
        font-size: {ThemeFonts.SIZE_BODY}px;
    }}
    QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {ThemeColors.BORDER_FOCUS};
    }}

    /* ================================================================
       COMBOBOX
       ================================================================ */
    QComboBox {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.MD}px;
        padding: 4px 28px 4px 12px;
        min-height: 28px;
    }}
    QComboBox:hover {{
        border-color: {ThemeColors.BORDER_LIGHT};
    }}
    QComboBox:focus {{
        border-color: {ThemeColors.BORDER_FOCUS};
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
        border-radius: {ThemeRadius.MD}px;
    }}

    /* ================================================================
       CHECKBOX
       ================================================================ */
    QCheckBox {{
        color: {ThemeColors.TEXT_PRIMARY};
        spacing: {ThemeSpacing.SM}px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: {ThemeRadius.SM}px;
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

    /* ================================================================
       PROGRESS BAR
       ================================================================ */
    QProgressBar {{
        background-color: {ThemeColors.BG_SURFACE};
        border: none;
        border-radius: 5px;
        min-height: 10px;
        max-height: 10px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background-color: {ThemeColors.PRIMARY};
        border-radius: 5px;
    }}

    /* ================================================================
       SCROLLBARS — thin, rounded, subtle
       ================================================================ */
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

    /* ================================================================
       TREE VIEW
       ================================================================ */
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
        image: url({_ARROW_RIGHT});
    }}
    QTreeView::branch:open:has-children:!has-siblings,
    QTreeView::branch:open:has-children:has-siblings {{
        border-image: none;
        image: url({_ARROW_DOWN});
    }}
    QTreeView::branch:has-siblings:!adjoins-item,
    QTreeView::branch:has-siblings:adjoins-item,
    QTreeView::branch:!has-children:!has-siblings:adjoins-item {{
        border-image: none;
        image: none;
    }}

    /* ================================================================
       LIST WIDGET
       ================================================================ */
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

    /* ================================================================
       SCROLL AREA
       ================================================================ */
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}

    /* ================================================================
       SPLITTER — highlight handle on hover
       ================================================================ */
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

    /* ================================================================
       MENU
       ================================================================ */
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

    /* ================================================================
       DIALOG
       ================================================================ */
    QDialog {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_PRIMARY};
    }}

    /* ================================================================
       TOOLTIP
       ================================================================ */
    QToolTip {{
        background-color: {ThemeColors.BG_ELEVATED};
        color: {ThemeColors.TEXT_PRIMARY};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: {ThemeRadius.SM}px;
        padding: 4px 8px;
        font-size: {ThemeFonts.SIZE_CAPTION}px;
    }}

    /* ================================================================
       GROUP BOX
       ================================================================ */
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

    /* ================================================================
       STATUS BAR  (footer)
       ================================================================ */
    QStatusBar {{
        background-color: {ThemeColors.BG_SURFACE};
        color: {ThemeColors.TEXT_SECONDARY};
        border-top: 1px solid {ThemeColors.BORDER};
        font-size: {ThemeFonts.SIZE_CAPTION}px;
        min-height: 28px;
        max-height: 32px;
    }}
    QStatusBar::item {{
        border: none;
    }}
    """
