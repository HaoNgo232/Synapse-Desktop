"""
Tests cho mcp_server/utils/logging_utils.py

Kiem tra force_all_logging_to_stderr redirect logging dung:
- Root logger handlers ghi ra stderr
- stdout handlers bi thay the boi stderr handlers
"""

import logging
import sys

from mcp_server.utils.logging_utils import force_all_logging_to_stderr


class TestForceAllLoggingToStderr:
    """Kiem tra force_all_logging_to_stderr chuyen het logging sang stderr."""

    def test_root_logger_has_stderr_handler(self):
        """Sau khi goi, root logger phai co handler ghi ra stderr."""
        force_all_logging_to_stderr()

        root = logging.getLogger()
        stderr_handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.StreamHandler)
            and getattr(h, "stream", None) is sys.stderr
        ]
        assert len(stderr_handlers) >= 1

    def test_root_logger_no_stdout_handler(self):
        """Root logger khong con handler nao ghi ra stdout."""
        force_all_logging_to_stderr()

        root = logging.getLogger()
        stdout_handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.StreamHandler)
            and getattr(h, "stream", None) is sys.stdout
        ]
        assert len(stdout_handlers) == 0

    def test_root_logger_level_is_info(self):
        """Root logger duoc set level INFO."""
        force_all_logging_to_stderr()

        root = logging.getLogger()
        assert root.level == logging.INFO
