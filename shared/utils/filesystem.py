"""
Shared Filesystem Utilities - OS-neutral path and file checks.
"""

import os
import platform
import re
from pathlib import Path
from shared.constants import BINARY_EXTENSIONS

# Pre-compile regex for is_system_path (module-level optimization)
_WINDOWS_RESERVED_PATTERN = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", re.IGNORECASE
)

# Optimization: Module-level constants
_TEXT_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".sh",
        ".sql",
        ".mod",
        ".sum",
        ".toml",
        ".cfg",
        ".ini",
        ".env",
        ".jsx",
        ".tsx",
        ".vue",
        ".svelte",
        ".scss",
        ".less",
        ".graphql",
        ".proto",
        ".tf",
        ".dockerfile",
    }
)


def is_binary_file(path_or_str: Path | str) -> bool:
    """Check if a file is binary using suffix and magic bytes."""
    path_str = str(path_or_str)
    _, ext = os.path.splitext(path_str)
    ext = ext.lower()

    # 1. Fast check by extension
    if ext in BINARY_EXTENSIONS:
        return True

    # Whitelist common text extensions
    if ext in _TEXT_EXTENSIONS:
        return False

    # 2. Fallback to magic bytes check
    try:
        if os.path.getsize(path_str) > 5 * 1024 * 1024:
            return True

        with open(path_str, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except (PermissionError, OSError):
        return False


def is_system_path_str(path_str: str) -> bool:
    """Fast check for OS system paths using string matching."""
    system = platform.system()
    name = os.path.basename(path_str)

    if system == "Windows":
        if _WINDOWS_RESERVED_PATTERN.match(name):
            return True
        lower_path = path_str.lower()
        if "\\windows\\" in lower_path or "\\system32\\" in lower_path:
            return True
    elif system == "Darwin":  # macOS
        if name in (".DS_Store", ".Trashes", ".fseventsd") or name.startswith(
            ".Spotlight-"
        ):
            return True
    elif system == "Linux":
        if path_str.startswith(("/proc/", "/sys/", "/dev/")):
            return True

    return False


def is_system_path(file_path: Path) -> bool:
    """Check if path is an OS system path."""
    return is_system_path_str(str(file_path))
