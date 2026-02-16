"""
Dark Mode OLED Theme - Core Design System

Centralized theme configuration following UI/UX Pro Max guidelines.
Style: Dark Mode (OLED) + Minimalism for Developer Tools
"""

from PySide6.QtGui import QFont, QFontDatabase
from pathlib import Path


class ThemeFonts:
    """Typography System - JetBrains Mono + IBM Plex Sans"""

    _fonts_loaded = False

    @staticmethod
    def load_fonts():
        """Load custom fonts from assets (call once at startup)"""
        if ThemeFonts._fonts_loaded:
            return

        font_dir = Path(__file__).parent.parent / "assets" / "fonts"

        # Load JetBrains Mono
        QFontDatabase.addApplicationFont(str(font_dir / "JetBrainsMono-Regular.ttf"))
        QFontDatabase.addApplicationFont(str(font_dir / "JetBrainsMono-Bold.ttf"))

        # Load IBM Plex Sans
        QFontDatabase.addApplicationFont(str(font_dir / "IBMPlexSans-Regular.ttf"))
        QFontDatabase.addApplicationFont(str(font_dir / "IBMPlexSans-SemiBold.ttf"))

        ThemeFonts._fonts_loaded = True

    # Heading fonts (for titles, section headers)
    HEADING_LARGE = QFont("JetBrains Mono", 18, QFont.Weight.Bold)
    HEADING_MEDIUM = QFont("JetBrains Mono", 14, QFont.Weight.Bold)
    HEADING_SMALL = QFont("JetBrains Mono", 12, QFont.Weight.DemiBold)

    # Body fonts (for descriptions, labels)
    BODY_LARGE = QFont("IBM Plex Sans", 12, QFont.Weight.Normal)
    BODY_MEDIUM = QFont("IBM Plex Sans", 11, QFont.Weight.Normal)
    BODY_SMALL = QFont("IBM Plex Sans", 10, QFont.Weight.Normal)

    # Code fonts (for file paths, code snippets)
    CODE = QFont("JetBrains Mono", 10, QFont.Weight.Normal)


class ThemeColors:
    """Dark Mode OLED Theme Colors - Developer Tools Edition"""

    # Primary - Blue 600/700 (giam do sang de tang tuong phan tren nen dark)
    PRIMARY = "#2563EB"  # Blue 600
    PRIMARY_HOVER = "#1D4ED8"  # Blue 700
    PRIMARY_PRESSED = "#1E40AF"  # Blue 800

    # Backgrounds - OLED Deep Black
    BG_PAGE = "#0F172A"  # Slate 900 - Main background
    BG_SURFACE = "#1E293B"  # Slate 800 - Cards, panels
    BG_ELEVATED = "#334155"  # Slate 700 - Hover states
    BG_HOVER = "#475569"  # Slate 600 - Interactive hover

    # Text - High Contrast on Dark
    TEXT_PRIMARY = "#F1F5F9"  # Slate 100 - Main text
    TEXT_SECONDARY = "#94A3B8"  # Slate 400 - Muted text
    TEXT_MUTED = "#64748B"  # Slate 500 - Very muted

    # Borders - Subtle on Dark
    BORDER = "#334155"  # Slate 700
    BORDER_FOCUS = "#2563EB"  # Blue 600 - cung voi PRIMARY
    BORDER_LIGHT = "#475569"  # Slate 600 - Lighter border

    # Status (text/border)
    SUCCESS = "#10B981"  # Emerald 500
    WARNING = "#F59E0B"  # Amber 500
    ERROR = "#EF4444"  # Red 500

    # Semantic button backgrounds - ghi de len global, phan biet nut dac thu
    ERROR_BG = "#DC2626"  # Red 600 - nut danger/delete
    ERROR_BG_HOVER = "#B91C1C"  # Red 700
    SUCCESS_BG = "#059669"  # Emerald 600 - nut success/confirm
    SUCCESS_BG_HOVER = "#047857"  # Emerald 700
    WARNING_BG = "#D97706"  # Amber 600 - nut canh bao
    WARNING_BG_HOVER = "#B45309"  # Amber 700

    # Icons
    ICON_FOLDER = "#F59E0B"  # Amber 500
    ICON_FILE = "#64748B"  # Slate 500

    # Search
    SEARCH_HIGHLIGHT = "#422006"  # Amber 950 - Dark amber bg


class ThemeSpacing:
    """Spacing constants for consistent layouts"""

    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    XXL = 24


class ThemeRadius:
    """Border radius constants"""

    SM = 4
    MD = 6
    LG = 8
    XL = 12
