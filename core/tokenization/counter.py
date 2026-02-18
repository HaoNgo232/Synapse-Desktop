"""
Core token counting logic.

Functions:
- count_tokens(): Dem tokens trong text (auto-detect encoder)
- count_tokens_for_file(): Dem tokens trong file (co cache + mtime)
- _count_tokens_for_file_no_cache(): Dem KHONG update cache (parallel-safe)
- _read_file_mmap(): Doc file bang mmap (nhanh hon read() 15-50%)

Encoder management nam o core.encoders (SRP).
Cache management nam o core.tokenization.cache (SRP).
"""

import mmap
from pathlib import Path
from typing import Optional

from core.encoders import _estimate_tokens
from core.tokenization.encoder_registry import get_encoder
from core.tokenization.cache import token_cache

# Guardrail: skip files > 5MB
MAX_BYTES = 5 * 1024 * 1024


def count_tokens(text: str) -> int:
    """
    Dem so token trong mot doan text.

    Auto-detect model:
    - Model co tokenizer_repo -> Dung Hugging Face tokenizers
    - Model khac -> Dung rs-bpe/tiktoken

    Args:
        text: Text can dem token

    Returns:
        So luong tokens
    """
    encoder = get_encoder()

    # Neu encoder khong kha dung, dung uoc luong
    if encoder is None:
        return _estimate_tokens(text)

    try:
        # Import _encoder_type tu module state
        import core.encoders as _enc

        # Hugging Face tokenizer dung .encode().ids
        if _enc._encoder_type == "hf":
            return len(encoder.encode(text).ids)
        # rs-bpe va tiktoken dung .encode()
        else:
            return len(encoder.encode(text))
    except Exception:
        # Fallback neu encode that bai
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
            # Check empty file
            if f.seek(0, 2) == 0:
                return ""
            f.seek(0)

            # mmap file vao memory
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                content_bytes = mm.read()
                return content_bytes.decode("utf-8", errors="replace")
    except Exception:
        # Fallback ve read() thong thuong neu mmap fail
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None


def _count_tokens_for_file_no_cache(file_path: Path) -> int:
    """
    Dem token cho file KHONG update cache.

    Dung cho parallel processing - tranh lock contention.
    Caller chiu trach nhiem update cache sau.

    Args:
        file_path: Duong dan file

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

        # Check binary su dung comprehensive detection
        from core.utils.file_utils import is_binary_file

        if is_binary_file(file_path):
            return 0

        # Doc voi mmap (nhanh hon)
        content = _read_file_mmap(file_path)
        if content is None:
            return 0

        return count_tokens(content)

    except Exception:
        return 0


def count_tokens_for_file(file_path: Path) -> int:
    """
    Dem so token trong mot file.

    - Skip files qua lon (> 5MB)
    - Skip binary files
    - Return 0 neu khong doc duoc
    - Uses LRU mtime-based caching cho performance

    Args:
        file_path: Duong dan den file

    Returns:
        So luong tokens, hoac 0 neu skip/error
    """
    try:
        # Check file exists
        if not file_path.exists():
            return 0

        if not file_path.is_file():
            return 0

        # Check file size truoc (cheap operation)
        stat = file_path.stat()
        if stat.st_size > MAX_BYTES:
            return 0

        # Empty files
        if stat.st_size == 0:
            return 0

        path_str = str(file_path)

        # Check cache voi LRU management
        cached = token_cache.get(path_str, stat.st_mtime)
        if cached is not None:
            return cached

        # Check binary su dung comprehensive detection
        from core.utils.file_utils import is_binary_file

        if is_binary_file(file_path):
            return 0

        # Doc va dem
        content = file_path.read_text(encoding="utf-8", errors="replace")
        token_count = count_tokens(content)

        # Update cache (LRU eviction tu dong trong TokenCache.put())
        token_cache.put(path_str, stat.st_mtime, token_count)

        return token_count

    except (OSError, IOError):
        return 0
