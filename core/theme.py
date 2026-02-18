"""
Synapse Desktop Design System — Dark Theme

Inspired by VS Code / JetBrains dark themes.
Centralized color palette, typography, spacing, and radius tokens.
All views and components reference these constants for visual consistency.
"""

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from pathlib import Path


class ThemeFonts:
    """Typography System — Segoe UI / SF Pro + Cascadia Code"""

    _fonts_loaded = False

    # Font family stacks
    FAMILY_BODY = '"Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif'
    FAMILY_MONO = '"Cascadia Code", "Fira Code", "Consolas", monospace'

    @staticmethod
    def load_fonts():
        """Load custom fonts from assets (call once at startup)."""
        if ThemeFonts._fonts_loaded:
            return

        font_dir = Path(__file__).parent.parent / "assets" / "fonts"

        # Load custom fonts tu assets/fonts (dam bao nhat quan giua cac may)
        # Cascadia Code: monospace font cho code display (MIT license, Microsoft)
        # IBM Plex Sans: body text font
        for name in (
            "CascadiaCode-Regular.ttf",
            "CascadiaCode-Bold.ttf",
            "IBMPlexSans-Regular.ttf",
            "IBMPlexSans-SemiBold.ttf",
        ):
            path = font_dir / name
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))

        ThemeFonts._fonts_loaded = True

    # Size scale (px): 11 caption → 13 body → 15 subtitle → 18 title → 24 heading
    SIZE_CAPTION = 11
    SIZE_BODY = 13
    SIZE_SUBTITLE = 15
    SIZE_TITLE = 18
    SIZE_HEADING = 24

    # Pre-built QFont objects
    HEADING_LARGE = QFont("Segoe UI", 24, QFont.Weight.Bold)
    HEADING_MEDIUM = QFont("Segoe UI", 18, QFont.Weight.Bold)
    HEADING_SMALL = QFont("Segoe UI", 15, QFont.Weight.DemiBold)

    BODY_LARGE = QFont("Segoe UI", 15, QFont.Weight.Normal)
    BODY_MEDIUM = QFont("Segoe UI", 13, QFont.Weight.Normal)
    BODY_SMALL = QFont("Segoe UI", 11, QFont.Weight.Normal)

    CODE = QFont("Cascadia Code", 13, QFont.Weight.Normal)
    CODE_SMALL = QFont("Cascadia Code", 11, QFont.Weight.Normal)


class ThemeColors:
    """
    Dark Theme Color Palette — VS Code / JetBrains inspired.

    Naming convention kept backward-compatible with existing codebase.
    """

    # ── Accent (tím pastel — buttons, selected, focus rings) ──
    PRIMARY = "#7C6FFF"
    PRIMARY_HOVER = "#6B5FEE"
    PRIMARY_PRESSED = "#5A4FDD"
    ACCENT = PRIMARY  # alias

    # ── Backgrounds ──
    BG_PAGE = "#1E1E2E"  # base — main window background
    BG_SURFACE = "#262637"  # surface — panels, sidebars, cards
    BG_ELEVATED = "#2D2D44"  # elevated surface — hover, dropdowns
    BG_HOVER = "#363652"  # interactive hover on elevated

    # ── Text ──
    TEXT_PRIMARY = "#E0E0F0"
    TEXT_SECONDARY = "#8888AA"
    TEXT_MUTED = "#666688"  # very muted (disabled, hints)

    # ── Borders ──
    BORDER = "#3E3E5E"  # subtle
    BORDER_FOCUS = "#5E5EFF"  # accent — focus rings
    BORDER_LIGHT = "#4E4E6E"  # slightly lighter

    # ── Status colors (text / icons) ──
    SUCCESS = "#4ADE80"
    WARNING = "#FBBF24"
    ERROR = "#F87171"
    INFO = "#60A5FA"

    # ── Semantic button backgrounds ──
    ERROR_BG = "#DC2626"
    ERROR_BG_HOVER = "#B91C1C"
    SUCCESS_BG = "#059669"
    SUCCESS_BG_HOVER = "#047857"
    WARNING_BG = "#D97706"
    WARNING_BG_HOVER = "#B45309"
    INFO_BG = "#2563EB"
    INFO_BG_HOVER = "#1D4ED8"

    # ── File tree icons ──
    ICON_FOLDER = "#FBBF24"
    ICON_FILE = "#8888AA"

    # ── Search highlight ──
    SEARCH_HIGHLIGHT = "#422006"

    # ── Tab bar specific ──
    TAB_ACTIVE_BG = "#2D2D44"
    TAB_ACTIVE_BORDER = "#7C6FFF"
    TAB_INACTIVE_TEXT = "#8888AA"


class ThemeSpacing:
    """8-px grid spacing system."""

    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class ThemeRadius:
    """Border radius tokens."""

    SM = 4
    MD = 6  # small buttons
    LG = 8  # cards
    XL = 12  # large panels


def generate_stylesheet() -> str:
    """Generate global QSS from the centralized theme system."""
    from core.theme_qss import generate_app_stylesheet

    return generate_app_stylesheet()


def apply_theme(app: QApplication) -> None:
    """Apply the global design-system stylesheet to the QApplication."""
    app.setStyleSheet(generate_stylesheet())
