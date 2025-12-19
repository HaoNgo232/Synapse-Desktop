"""
Dark Mode OLED Theme - Core Design System

Centralized theme configuration following UI/UX Pro Max guidelines.
Style: Dark Mode (OLED) + Minimalism for Developer Tools
"""


class ThemeColors:
    """Dark Mode OLED Theme Colors - Developer Tools Edition"""

    # Primary - Blue 500
    PRIMARY = "#3B82F6"
    PRIMARY_HOVER = "#2563EB"

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
    BORDER_FOCUS = "#3B82F6"  # Blue 500
    BORDER_LIGHT = "#475569"  # Slate 600 - Lighter border

    # Status
    SUCCESS = "#10B981"  # Emerald 500
    WARNING = "#F59E0B"  # Amber 500
    ERROR = "#EF4444"  # Red 500

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
