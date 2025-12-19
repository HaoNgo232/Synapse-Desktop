"""
Logging Configuration - Centralized logging setup

Cung cấp logging nhất quán cho toàn bộ app.
Log file được lưu tại ~/.overwrite-desktop/logs/
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Log directory
LOG_DIR = Path.home() / ".overwrite-desktop" / "logs"

# Logger singleton
_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """
    Get hoặc tạo logger singleton.
    
    Returns:
        Configured logger instance
    """
    global _logger
    
    if _logger is not None:
        return _logger
    
    _logger = logging.getLogger("overwrite-desktop")
    _logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers
    if _logger.handlers:
        return _logger
    
    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "[%(levelname)s] %(message)s"
    )
    console_handler.setFormatter(console_format)
    _logger.addHandler(console_handler)
    
    # File handler (DEBUG level)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        log_file = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        _logger.addHandler(file_handler)
    except (OSError, IOError) as e:
        # Log to console if file logging fails
        _logger.warning(f"Could not create log file: {e}")
    
    return _logger


def log_error(message: str, exc: Optional[Exception] = None):
    """Log error với optional exception details"""
    logger = get_logger()
    if exc:
        logger.error(f"{message}: {exc}", exc_info=True)
    else:
        logger.error(message)


def log_warning(message: str):
    """Log warning"""
    get_logger().warning(message)


def log_info(message: str):
    """Log info"""
    get_logger().info(message)


def log_debug(message: str):
    """Log debug"""
    get_logger().debug(message)