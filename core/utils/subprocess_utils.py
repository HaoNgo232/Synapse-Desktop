"""
Subprocess Utilities — Windows-safe subprocess execution.

On Windows (especially in PyInstaller EXE builds), every subprocess.run()
or subprocess.Popen() call opens a visible console window for a split second.
This causes a distracting "flashing black window" effect.

This module provides a drop-in wrapper that automatically adds the
CREATE_NO_WINDOW creation flag on Windows, preventing the flash.

Usage:
    from core.utils.subprocess_utils import run_subprocess

    result = run_subprocess(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(workspace_path),
        capture_output=True,
        text=True,
        timeout=5,
    )
"""

import subprocess
import platform
from typing import Any


# Pre-compute the flag once at import time.
# subprocess.CREATE_NO_WINDOW = 0x08000000 (Windows only).
_IS_WINDOWS = platform.system() == "Windows"
_NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0


def run_subprocess(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    """
    Wrapper around subprocess.run() that suppresses console windows on Windows.

    Accepts the same arguments as subprocess.run(). The `creationflags`
    keyword is automatically set to CREATE_NO_WINDOW on Windows unless
    the caller explicitly provides a different value.

    Returns:
        subprocess.CompletedProcess — identical to subprocess.run().
    """
    if _IS_WINDOWS and "creationflags" not in kwargs:
        kwargs["creationflags"] = _NO_WINDOW_FLAGS

    return subprocess.run(*args, **kwargs)


def popen_subprocess(*args: Any, **kwargs: Any) -> subprocess.Popen:
    """
    Wrapper around subprocess.Popen() that suppresses console windows on Windows.

    Useful for long-running subprocesses or streaming output.

    Returns:
        subprocess.Popen instance.
    """
    if _IS_WINDOWS and "creationflags" not in kwargs:
        kwargs["creationflags"] = _NO_WINDOW_FLAGS

    return subprocess.Popen(*args, **kwargs)