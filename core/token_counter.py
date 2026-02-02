"""
Token Counter - Dem token su dung tiktoken

Don gian hoa dang ke vi tiktoken la Python native library (OpenAI official).
"""

import os
import threading
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
# Using OrderedDict for LRU eviction
from collections import OrderedDict

_file_token_cache: OrderedDict[str, Tuple[float, int]] = OrderedDict()
_MAX_CACHE_SIZE = 2000  # Increased for better hit rate
_cache_lock = threading.Lock()

# Pre-compiled patterns for binary detection
_BINARY_SIGNATURES = [
    (b'\xFF\xD8\xFF', "JPEG"),
    (b'\x89PNG', "PNG"),
    (b'GIF8', "GIF"),
    (b'%PDF', "PDF"),
    (b'PK\x03\x04', "ZIP"),
    (b'\x7FELF', "ELF"),
    (b'MZ', "PE/EXE"),
]


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
    - Uses LRU mtime-based caching for performance

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

        # Check file size first (cheap operation)
        stat = file_path.stat()
        if stat.st_size > MAX_BYTES:
            return 0
        
        # Empty files
        if stat.st_size == 0:
            return 0

        path_str = str(file_path)
        
        # Check cache with LRU management
        with _cache_lock:
            cached = _file_token_cache.get(path_str)
            if cached is not None:
                cached_mtime, cached_count = cached
                if cached_mtime == stat.st_mtime:
                    # Move to end for LRU
                    _file_token_cache.move_to_end(path_str)
                    return cached_count

        # Check if binary using optimized detection
        with open(file_path, "rb") as f:
            chunk = f.read(8000)

        if _looks_binary_fast(chunk):
            return 0

        # Read and count
        content = file_path.read_text(encoding="utf-8", errors="replace")
        token_count = count_tokens(content)

        # Update cache with LRU eviction
        with _cache_lock:
            # Evict oldest if at capacity
            while len(_file_token_cache) >= _MAX_CACHE_SIZE:
                _file_token_cache.popitem(last=False)  # Remove oldest
            
            _file_token_cache[path_str] = (stat.st_mtime, token_count)
        
        return token_count

    except (OSError, IOError):
        return 0


def _looks_binary_fast(chunk: bytes) -> bool:
    """
    Optimized binary detection using pre-compiled signatures.
    """
    if len(chunk) == 0:
        return False
    
    # Check magic signatures first (fast path)
    for sig, _ in _BINARY_SIGNATURES:
        if chunk.startswith(sig):
            return True
    
    # Sample-based analysis for large chunks
    sample_size = min(len(chunk), 1000)
    sample = chunk[:sample_size]
    
    # Count null bytes and non-printable
    null_count = sample.count(b'\x00')
    if null_count > sample_size * 0.01:
        return True
    
    # Fast non-printable check using bytes translation
    non_printable = sum(1 for b in sample if b < 32 and b not in (9, 10, 13) or b > 126)
    if non_printable > sample_size * 0.3:
        return True
    
    return False


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
    
    PERFORMANCE FIX: Return early on cancellation, don't process remaining files.

    Args:
        file_paths: Danh sách đường dẫn files cần đếm token.

    Returns:
        Dict mapping path string -> token count.
    """
    from services.token_display import is_counting_tokens

    results: Dict[str, int] = {}
    
    # Check cancellation before starting
    if not is_counting_tokens():
        return results

    for i, path in enumerate(file_paths):
        # Check global cancellation flag EVERY file - CRITICAL for responsiveness
        if not is_counting_tokens():
            return results  # Return immediately with partial results

        try:
            results[str(path)] = count_tokens_for_file(path)
        except Exception:
            results[str(path)] = 0
        
        # Extra cancellation check every 3 files for even faster response
        if i > 0 and i % 3 == 0 and not is_counting_tokens():
            return results

    return results
