"""
Token Counter - Dem token su dung tiktoken

Don gian hoa dang ke vi tiktoken la Python native library (OpenAI official).
"""

import os
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
import tiktoken

# Lazy-loaded encoder singleton
_encoder: Optional[tiktoken.Encoding] = None

# Guardrail: skip files > 5MB
MAX_BYTES = 5 * 1024 * 1024

# File content cache: path -> (mtime, token_count)
_file_token_cache: Dict[str, Tuple[float, int]] = {}
_MAX_CACHE_SIZE = 1000


def _get_encoder() -> Optional[tiktoken.Encoding]:
    """
    Lay encoder singleton.

    Thử o200k_base (GPT-4o) trước, fallback sang cl100k_base (GPT-4/3.5)
    nếu không available (trong môi trường đóng gói như AppImage).

    Nếu không encoding nào hoạt động, return None và sử dụng ước lượng.
    """
    global _encoder
    if _encoder is None:
        # Danh sách encodings theo thứ tự ưu tiên
        encodings_to_try = ["o200k_base", "cl100k_base", "p50k_base", "gpt2"]

        for encoding_name in encodings_to_try:
            try:
                _encoder = tiktoken.get_encoding(encoding_name)
                break
            except Exception:
                continue

    return _encoder


def _estimate_tokens(text: str) -> int:
    """
    Ước lượng số token khi tiktoken không available.

    Quy tắc: ~4 ký tự = 1 token (heuristic phổ biến)
    Đây là ước lượng, không chính xác 100% nhưng đủ dùng.
    """
    if not text:
        return 0
    # Đếm cả whitespace và special chars
    return max(1, len(text) // 4)


@lru_cache(maxsize=256)
def _count_tokens_cached(text_hash: int, text_len: int) -> int:
    """Internal cached token counting by hash"""
    # This is called from count_tokens with hash as key
    # The actual text is passed separately
    return 0  # Placeholder, actual implementation below


def count_tokens(text: str) -> int:
    """
    Dem so token trong mot doan text.

    Args:
        text: Text can dem token

    Returns:
        So luong tokens
    """
    encoder = _get_encoder()

    # Nếu tiktoken không available, dùng ước lượng
    if encoder is None:
        return _estimate_tokens(text)

    try:
        return len(encoder.encode(text))
    except Exception:
        # Fallback nếu encode thất bại
        return _estimate_tokens(text)


def count_tokens_for_file(file_path: Path) -> int:
    """
    Dem so token trong mot file.

    - Skip files qua lon (> 5MB)
    - Skip binary files
    - Return 0 neu khong doc duoc
    - Uses mtime-based caching for performance

    Args:
        file_path: Duong dan den file

    Returns:
        So luong tokens, hoac 0 neu skip/error
    """
    global _file_token_cache

    try:
        # Check file exists
        if not file_path.exists():
            return 0

        if not file_path.is_file():
            return 0

        # Check file size
        stat = file_path.stat()
        if stat.st_size > MAX_BYTES:
            # File too large, skip silently (expected behavior)
            return 0

        # Check cache with mtime
        path_str = str(file_path)
        cached = _file_token_cache.get(path_str)
        if cached is not None:
            cached_mtime, cached_count = cached
            if cached_mtime == stat.st_mtime:
                return cached_count

        # Check if binary (read first 8KB)
        with open(file_path, "rb") as f:
            chunk = f.read(8000)

        if _looks_binary(chunk):
            return 0

        # Read and count
        content = file_path.read_text(encoding="utf-8", errors="replace")
        token_count = count_tokens(content)

        # Update cache (with size limit)
        if len(_file_token_cache) >= _MAX_CACHE_SIZE:
            # Remove oldest entries (first 20%)
            keys_to_remove = list(_file_token_cache.keys())[: _MAX_CACHE_SIZE // 5]
            for key in keys_to_remove:
                del _file_token_cache[key]

        _file_token_cache[path_str] = (stat.st_mtime, token_count)
        return token_count

    except (OSError, IOError):
        return 0


def clear_token_cache():
    """Clear the file token cache"""
    global _file_token_cache
    _file_token_cache.clear()


def clear_file_from_cache(path: str):
    """
    Xóa cache entry cho một file cụ thể.

    Gọi khi file watcher phát hiện file thay đổi,
    để lần tính token tiếp theo sẽ đọc lại file.

    Args:
        path: Đường dẫn file cần xóa khỏi cache
    """
    global _file_token_cache
    _file_token_cache.pop(path, None)


def _looks_binary(chunk: bytes) -> bool:
    """
    Kiem tra xem data co phai la binary khong.

    Logic port tu TypeScript:
    - Check magic numbers (PDF, ZIP, EXE, etc.)
    - Check ti le null bytes va non-printable characters
    """
    if len(chunk) == 0:
        return False

    # Check magic numbers
    if _check_magic_numbers(chunk):
        return True

    # Analyze byte content
    return _analyze_byte_content(chunk)


# Magic number signatures cho cac format binary pho bien
MAGIC_NUMBERS = [
    (bytes([0xFF, 0xD8, 0xFF]), "JPEG"),
    (bytes([0x89, 0x50, 0x4E, 0x47]), "PNG"),
    (bytes([0x47, 0x49, 0x46, 0x38]), "GIF"),
    (bytes([0x25, 0x50, 0x44, 0x46]), "PDF"),
    (bytes([0x50, 0x4B, 0x03, 0x04]), "ZIP"),
    (bytes([0x50, 0x4B, 0x05, 0x06]), "ZIP (empty)"),
    (bytes([0x7F, 0x45, 0x4C, 0x46]), "ELF"),
    (bytes([0x4D, 0x5A]), "PE/EXE"),
    (bytes([0xCA, 0xFE, 0xBA, 0xBE]), "Mach-O"),
]


def _check_magic_numbers(chunk: bytes) -> bool:
    """Check if chunk starts with known binary magic numbers"""
    for signature, _ in MAGIC_NUMBERS:
        if len(chunk) >= len(signature) and chunk[: len(signature)] == signature:
            return True
    return False


def _analyze_byte_content(chunk: bytes) -> bool:
    """
    Analyze byte content de detect binary.

    - > 1% null bytes -> binary
    - > 30% non-printable -> binary
    """
    if len(chunk) == 0:
        return False

    non_printable_count = 0
    null_byte_count = 0

    for byte in chunk:
        if byte == 0:
            null_byte_count += 1
        elif byte < 32 and byte not in (9, 10, 13):  # Exclude tab, LF, CR
            non_printable_count += 1
        elif byte > 126:
            non_printable_count += 1

    # > 1% null bytes -> binary
    if null_byte_count > len(chunk) * 0.01:
        return True

    # > 30% non-printable -> binary
    if non_printable_count > len(chunk) * 0.3:
        return True

    return False


# ============================================================================
# PARALLEL PROCESSING - Port from Repomix (src/shared/processConcurrency.ts)
# ============================================================================

# Worker initialization is expensive, so we prefer fewer threads unless there are many files
TASKS_PER_WORKER = 100

# Minimum number of files to trigger parallel processing
MIN_FILES_FOR_PARALLEL = 10


def get_worker_count(num_tasks: int) -> int:
    """
    Tinh so luong workers toi uu dua tren so luong tasks va CPU cores.

    Logic port tu Repomix:
    - Moi worker xu ly ~100 tasks.
    - Khong vuot qua so CPU cores.
    - Toi thieu 1 worker.

    Args:
        num_tasks: So luong tasks can xu ly.

    Returns:
        So luong workers toi uu.
    """
    cpu_count = os.cpu_count() or 4
    # ceil(num_tasks / TASKS_PER_WORKER) = (num_tasks + TASKS_PER_WORKER - 1) // TASKS_PER_WORKER
    calculated = (num_tasks + TASKS_PER_WORKER - 1) // TASKS_PER_WORKER
    return max(1, min(cpu_count, calculated))


def count_tokens_batch(file_paths: List[Path]) -> Dict[str, int]:
    """
    Đếm token cho nhiều files - SYNC version với global cancellation.

    Không dùng ThreadPoolExecutor để tránh race condition.
    Check global flag mỗi file để cancel ngay lập tức.

    Args:
        file_paths: Danh sách đường dẫn files cần đếm token.

    Returns:
        Dict mapping path string -> token count.
    """
    from services.token_display import is_counting_tokens

    results: Dict[str, int] = {}

    for path in file_paths:
        # Check global cancellation flag mỗi file - CRITICAL
        if not is_counting_tokens():
            break

        try:
            results[str(path)] = count_tokens_for_file(path)
        except Exception:
            results[str(path)] = 0

    return results
