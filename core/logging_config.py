"""
Logging Configuration - Centralized logging setup

Cung cấp logging nhất quán cho toàn bộ app.
Log file được lưu tại ~/.synapse-desktop/logs/

Optimized for production:
- Log rotation (max 5 files, 2MB each)
- Buffered writes (reduce disk I/O)
- INFO level for file (DEBUG only when needed)
"""

import logging
import logging.handlers
import sys
import os
from datetime import datetime
from typing import Optional

from config.paths import LOG_DIR, DEBUG_ENV_VAR, DEBUG_MODE

# Logger singleton
_logger: Optional[logging.Logger] = None

# Log rotation config
MAX_LOG_SIZE = 2 * 1024 * 1024  # 2MB per file
MAX_LOG_FILES = 5  # Keep 5 backup files
BUFFER_CAPACITY = 100  # Buffer 100 log records before flush


def get_logger() -> logging.Logger:
    """
    Get hoặc tạo logger singleton.

    Returns:
        Configured logger instance
    """
    global _logger

    if _logger is not None:
        return _logger

    _logger = logging.getLogger("synapse-desktop")
    _logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

    # Avoid duplicate handlers
    if _logger.handlers:
        return _logger

    # Console handler (INFO level, or DEBUG if debug mode)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    console_format = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_format)
    _logger.addHandler(console_handler)

    # File handler with rotation (INFO level normally, DEBUG if debug mode)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        log_file = LOG_DIR / "app.log"

        # Use RotatingFileHandler for automatic rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_SIZE,
            backupCount=MAX_LOG_FILES,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

        file_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_format)

        # Wrap with MemoryHandler for buffered writes (reduces disk I/O)
        memory_handler = logging.handlers.MemoryHandler(
            capacity=BUFFER_CAPACITY,
            flushLevel=logging.ERROR,  # Flush immediately on ERROR
            target=file_handler,
        )
        memory_handler.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

        _logger.addHandler(memory_handler)

    except (OSError, IOError) as e:
        # Log to console if file logging fails
        _logger.warning(f"Could not create log file: {e}")

    return _logger


def flush_logs():
    """
    Flush buffered logs to disk.
    Call this before app exit to ensure all logs are written.
    """
    if _logger:
        for handler in _logger.handlers:
            try:
                if isinstance(handler, logging.handlers.MemoryHandler):
                    handler.flush()
                elif hasattr(handler, "flush"):
                    handler.flush()
            except Exception:
                pass  # Ignore errors during shutdown


def set_debug_mode(enabled: bool):
    """
    Enable or disable debug mode at runtime.

    Args:
        enabled: True to enable DEBUG level logging
    """
    global DEBUG_MODE
    DEBUG_MODE = enabled

    if _logger:
        new_level = logging.DEBUG if enabled else logging.INFO
        _logger.setLevel(new_level)
        for handler in _logger.handlers:
            handler.setLevel(new_level)


def cleanup_old_logs(max_age_days: int = 7):
    """
    Remove log files older than max_age_days.
    Called periodically to prevent disk space issues.

    Args:
        max_age_days: Maximum age of log files to keep
    """
    if not LOG_DIR.exists():
        return

    import time

    cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

    try:
        for log_file in LOG_DIR.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
            except OSError:
                pass
    except Exception:
        pass


def log_error(message: str, exc: Optional[Exception] = None):
    """Log error với optional exception details"""
    logger = get_logger()
    if exc:
        logger.error(f"{message}: {exc}", exc_info=DEBUG_MODE)
    else:
        logger.error(message)


def log_warning(message: str):
    """Log warning"""
    get_logger().warning(message)


def log_info(message: str):
    """Log info"""
    get_logger().info(message)


def log_debug(message: str):
    """Log debug - only written if DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        get_logger().debug(message)
