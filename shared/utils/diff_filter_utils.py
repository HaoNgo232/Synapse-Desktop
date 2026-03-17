"""
Diff Filter Utilities.

Utility functions de danh dau cac file nen auto-exclude trong Copy Diff flow.
"""

import fnmatch

from shared.constants.file_patterns import (
    DIFF_AUTO_EXCLUDE_GLOBS,
    DIFF_AUTO_EXCLUDE_PATTERNS,
)


def should_auto_exclude(file_path: str) -> bool:
    """
    Check whether a file should be auto-excluded from diff output.

    The function supports exact filename matching and glob pattern matching.

    Args:
        file_path: Relative file path (example: "src/utils/helper.py")

    Returns:
        True if the file should be auto-excluded; otherwise False.
    """
    normalized = file_path.replace("\\", "/")
    filename = normalized.rsplit("/", 1)[-1]

    if filename in DIFF_AUTO_EXCLUDE_PATTERNS:
        return True

    for pattern in DIFF_AUTO_EXCLUDE_GLOBS:
        if fnmatch.fnmatch(filename, pattern):
            return True

    return False
