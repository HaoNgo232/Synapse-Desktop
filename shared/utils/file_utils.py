import os
import stat
import platform
import re
from pathlib import Path
from shared.constants import BINARY_EXTENSIONS

# Optimization: Module-level constants (tạo 1 lần duy nhất)
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

# Pre-compile regex for is_system_path (module-level optimization)
_WINDOWS_RESERVED_PATTERN = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", re.IGNORECASE
)


def is_binary_file(path_or_str: Path | str) -> bool:
    """
    Check xem một file có phải là binary không.
    Hàm này hỗ trợ cả Path object và string path để tối ưu hiệu năng trong vòng lặp lớn.

    Optimization:
    1. Kiểm tra extension trước (fast whitelist/blacklist)
    2. Chỉ đọc nội dung nếu extension không xác định.
    """
    # Convert to string for suffix check
    path_str = str(path_or_str)
    _, ext = os.path.splitext(path_str)
    ext = ext.lower()

    # 1. Fast check by extension
    if ext in BINARY_EXTENSIONS:
        return True

    # Whitelist các extension text phổ biến để skip I/O
    if ext in _TEXT_EXTENSIONS:
        return False

    # 2. Fallback to magic bytes check
    try:
        # Kiểm tra loại file bằng lstat trước khi mở để tránh bị treo (blocking) khi gặp Named Pipe (FIFO)
        stat_result = os.lstat(path_str)
        if not stat.S_ISREG(stat_result.st_mode):
            return False

        # Kiểm tra file size trước, file cực lớn (>5MB) mà không có extension
        # text thì khả năng cao là binary (ví dụ dump file).
        if stat_result.st_size > 5 * 1024 * 1024:
            return True

        with open(path_str, "rb") as f:
            chunk = f.read(1024)
            # Nếu chứa null byte thì khả năng cao là binary
            return b"\x00" in chunk
    except (PermissionError, OSError):
        return False


def is_binary_by_extension(file_path: Path) -> bool:
    """
    Check if file is binary based on extension (legacy function).
    Use is_binary_file() for more accurate detection.
    """
    return file_path.suffix.lower() in BINARY_EXTENSIONS


def is_system_path_str(path_str: str) -> bool:
    """
    Version nhanh của is_system_path nhận input là string.
    Dùng để tối ưu trong các vòng lặp quét hàng chục nghìn file.
    """
    system = platform.system()
    name = os.path.basename(path_str)

    if system == "Windows":
        # Check reserved names using pre-compiled regex
        if _WINDOWS_RESERVED_PATTERN.match(name):
            return True
        # Check system folders
        lower_path = path_str.lower()
        if "\\windows\\" in lower_path or "\\system32\\" in lower_path:
            return True

    elif system == "Darwin":  # macOS
        # Common macOS system files/folders
        if name in (".DS_Store", ".Trashes", ".fseventsd") or name.startswith(
            ".Spotlight-"
        ):
            return True

    elif system == "Linux":
        # Critical Linux system directories
        if path_str.startswith(("/proc/", "/sys/", "/dev/")):
            return True

    return False


def is_system_path(file_path: Path) -> bool:
    """
    Check if path is an OS system path that should be excluded.
    Supports: Windows, macOS, Linux
    """
    return is_system_path_str(str(file_path))
