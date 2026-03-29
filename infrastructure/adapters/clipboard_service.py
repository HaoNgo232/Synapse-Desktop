"""
Clipboard Service - Implementation sử dụng Qt.
"""

import logging

logger = logging.getLogger(__name__)


class QtClipboardService:
    """
    Clipboard service sử dụng Qt QApplication.clipboard().
    """

    def copy_to_clipboard(self, text: str) -> tuple[bool, str]:
        """
        Copy text ra system clipboard qua Qt.

        Returns:
            (success, error_message): (True, "") if success, (False, error_msg) if failed
        """
        try:
            from PySide6.QtWidgets import QApplication

            clipboard = QApplication.clipboard()
            if clipboard is None:
                msg = "QApplication.clipboard() returned None"
                logger.warning(msg)
                return False, msg

            clipboard.setText(text)
            return True, ""
        except Exception as e:
            msg = f"Clipboard error: {e}"
            logger.warning("Failed to copy to clipboard: %s", e)
            return False, msg
