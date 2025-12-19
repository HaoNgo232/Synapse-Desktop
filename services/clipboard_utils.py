"""
Clipboard Utilities - Safe clipboard operations với fallback

Xử lý các trường hợp clipboard không hoạt động trên một số systems.
"""

from typing import Tuple
from core.logging_config import log_error, log_warning


def copy_to_clipboard(text: str) -> Tuple[bool, str]:
    """
    Copy text to clipboard với error handling.

    Args:
        text: Text cần copy

    Returns:
        Tuple (success: bool, message: str)
    """
    # Try pyperclip first
    try:
        import pyperclip

        pyperclip.copy(text)
        return True, "Copied to clipboard"
    except Exception as e:
        log_warning(f"pyperclip failed: {e}")

    # Fallback: Try xclip on Linux
    try:
        import subprocess
        import sys

        if sys.platform.startswith("linux"):
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            process.communicate(text.encode("utf-8"))
            if process.returncode == 0:
                return True, "Copied to clipboard (xclip)"
    except FileNotFoundError:
        pass
    except Exception as e:
        log_warning(f"xclip fallback failed: {e}")

    # Fallback: Try xsel on Linux
    try:
        import subprocess
        import sys

        if sys.platform.startswith("linux"):
            process = subprocess.Popen(
                ["xsel", "--clipboard", "--input"],
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            process.communicate(text.encode("utf-8"))
            if process.returncode == 0:
                return True, "Copied to clipboard (xsel)"
    except FileNotFoundError:
        pass
    except Exception as e:
        log_warning(f"xsel fallback failed: {e}")

    # All methods failed
    log_error("All clipboard methods failed")
    return False, "Clipboard not available. Install xclip or xsel on Linux."


def get_clipboard_text() -> Tuple[bool, str]:
    """
    Get text from clipboard với error handling.

    Returns:
        Tuple (success: bool, text_or_error: str)
    """
    try:
        import pyperclip

        text = pyperclip.paste()
        # pyperclip.paste() có thể trả về None
        if text is None:
            return False, "Clipboard is empty"
        return True, text
    except Exception as e:
        log_error(f"Failed to read clipboard: {e}")
        return False, f"Cannot read clipboard: {e}"
