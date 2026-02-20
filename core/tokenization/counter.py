"""
Core token counting logic - Pure functions.

REFACTORED: Toan bo global state (_default_encoder, _default_tokenizer_repo)
da duoc chuyen sang services.tokenization_service.TokenizationService.

Module nay chi chua cac ham thuan tuy (pure functions):
- count_tokens(): Dem tokens trong text voi encoder da cho
- count_tokens_for_file(): Dem tokens trong file (co cache + mtime)
- _count_tokens_for_file_no_cache(): Dem KHONG update cache (parallel-safe)
- _read_file_mmap(): Doc file bang mmap (nhanh hon read() 15-50%)

DIP: Module nay KHONG import tu services layer.
Encoder duoc truyen tu caller (TokenizationService).
"""

import mmap
from pathlib import Path
from typing import Optional, Any

from core.encoders import _estimate_tokens
from core.tokenization.cache import token_cache

# Guardrail: skip files > 5MB
MAX_BYTES = 5 * 1024 * 1024


def count_tokens(
    text: str,
    encoder: Optional[Any] = None,
    encoder_type: str = "",
) -> int:
    """
    Dem so token trong text voi encoder da cho.

    Ham thuan tuy (pure function) - khong su dung global state.
    Caller chiu trach nhiem truyen encoder phu hop.

    Args:
        text: Text can dem token
        encoder: Encoder instance (bat buoc cho ket qua chinh xac)
        encoder_type: Loai encoder ("hf", "rs_bpe", "tiktoken")

    Returns:
        So luong tokens
    """
    if encoder is None:
        return _estimate_tokens(text)

    try:
        if encoder_type == "hf":
            return len(encoder.encode(text).ids)
        else:
            return len(encoder.encode(text))
    except Exception:
        return _estimate_tokens(text)


def _read_file_mmap(file_path: Path) -> Optional[str]:
    """
    Doc file su dung mmap - nhanh hon read() thong thuong.

    mmap map file truc tiep vao virtual memory,
    giam so lan copy data giua kernel va user space.

    Args:
        file_path: Duong dan file can doc

    Returns:
        Content cua file hoac None neu khong doc duoc
    """
    try:
        with open(file_path, "rb") as f:
            if f.seek(0, 2) == 0:
                return ""
            f.seek(0)
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                content_bytes = mm.read()
                return content_bytes.decode("utf-8", errors="replace")
    except Exception:
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None


def _count_tokens_for_file_no_cache(
    file_path: Path,
    encoder: Optional[Any] = None,
    encoder_type: str = "",
) -> int:
    """
    Dem token cho file KHONG update cache.

    Dung cho parallel processing - tranh lock contention.
    Caller chiu trach nhiem update cache sau.

    Args:
        file_path: Duong dan file
        encoder: Encoder instance
        encoder_type: Loai encoder

    Returns:
        So token hoac 0 neu khong dem duoc
    """
    try:
        if not file_path.exists() or not file_path.is_file():
            return 0

        stat = file_path.stat()
        if stat.st_size > MAX_BYTES or stat.st_size == 0:
            return 0

        path_str = str(file_path)

        # Check cache truoc (read-only, khong move LRU)
        cached = token_cache.get_no_move(path_str, stat.st_mtime)
        if cached is not None:
            return cached

        from core.utils.file_utils import is_binary_file

        if is_binary_file(file_path):
            return 0

        content = _read_file_mmap(file_path)
        if content is None:
            return 0

        return count_tokens(content, encoder=encoder, encoder_type=encoder_type)

    except Exception:
        return 0


def count_tokens_for_file(
    file_path: Path,
    encoder: Optional[Any] = None,
    encoder_type: str = "",
) -> int:
    """
    Dem so token trong mot file voi cache.

    - Skip files qua lon (> 5MB)
    - Skip binary files
    - Return 0 neu khong doc duoc
    - Uses LRU mtime-based caching

    Args:
        file_path: Duong dan den file
        encoder: Encoder instance
        encoder_type: Loai encoder

    Returns:
        So luong tokens, hoac 0 neu skip/error
    """
    try:
        if not file_path.exists() or not file_path.is_file():
            return 0

        stat = file_path.stat()
        if stat.st_size > MAX_BYTES or stat.st_size == 0:
            return 0

        path_str = str(file_path)

        # Check cache voi LRU management
        cached = token_cache.get(path_str, stat.st_mtime)
        if cached is not None:
            return cached

        from core.utils.file_utils import is_binary_file

        if is_binary_file(file_path):
            return 0

        content = file_path.read_text(encoding="utf-8", errors="replace")
        token_count = count_tokens(
            content, encoder=encoder, encoder_type=encoder_type
        )

        token_cache.put(path_str, stat.st_mtime, token_count)
        return token_count

    except (OSError, IOError):
        return 0
