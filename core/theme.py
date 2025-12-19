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

    # Text - High Contrast on Dark
    TEXT_PRIMARY = "#F1F5F9"  # Slate 100 - Main text
    TEXT_SECONDARY = "#94A3B8"  # Slate 400 - Muted text
    TEXT_MUTED = "#64748B"  # Slate 500 - Very muted

    # Borders - Subtle on Dark
    BORDER = "#334155"  # Slate 700
    BORDER_FOCUS = "#3B82F6"  # Blue 500

    # Status
    SUCCESS = "#10B981"  # Emerald 500
    WARNING = "#F59E0B"  # Amber 500
    ERROR = "#EF4444"  # Red 500

    # Icons
    ICON_FOLDER = "#F59E0B"  # Amber 500
    ICON_FILE = "#64748B"  # Slate 500

    # Search
    SEARCH_HIGHLIGHT = "#422006"  # Amber 950 - Dark amber bg
