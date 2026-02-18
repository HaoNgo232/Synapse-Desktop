"""
Token Counter - Dem token su dung encoder tu core.encoders.

Module nay tap trung vao COUNTING logic:
- count_tokens(): Dem tokens trong text
- count_tokens_for_file(): Dem tokens trong file (co cache)
- count_tokens_batch(): Batch counting (sequential)
- count_tokens_batch_parallel(): Batch counting song song
- count_tokens_batch_hf(): Batch counting voi HF tokenizer (cuc nhanh)

Encoder management da duoc tach sang core.encoders (SRP).
Binary detection da duoc tach sang core.binary_detection (SRP).
"""

import os
import mmap
import threading
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from collections import OrderedDict

# Import tu modules da tach (SRP)
from core.encoders import (
    _get_encoder,
    _get_hf_tokenizer,
    _get_tokenizer_repo,
    _estimate_tokens,
    reset_encoder,
    HAS_TOKENIZERS,
    _encoder_type,
)

# Re-export de backward compatibility
from core.encoders import reset_encoder  # noqa: F811

# Guardrail: skip files > 5MB
MAX_BYTES = 5 * 1024 * 1024

# File content cache: path -> (mtime, token_count)
# Su dung OrderedDict cho LRU eviction
_file_token_cache: OrderedDict[str, Tuple[float, int]] = OrderedDict()
_MAX_CACHE_SIZE = 2000  # Tang de hit rate tot hon
_cache_lock = threading.Lock()


# ============================================================================
# CORE COUNTING - Dem tokens trong text
# ============================================================================


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
    encoder = _get_encoder()

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


# ============================================================================
# MMAP FILE READING - Nhanh hon read() 15-50%
# ============================================================================


def _read_file_mmap(file_path: Path) -> Optional[str]:
    """
    Doc file su dung mmap - nhanh hon read() thong thuong.

    mmap map file truc tiep vao virtual memory,
    giam so lan copy data giua kernel va user space.

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


# ============================================================================
# FILE TOKEN COUNTING - Dem tokens trong file voi cache
# ============================================================================


def _count_tokens_for_file_no_cache(file_path: Path) -> int:
    """
    Dem token cho file KHONG update cache.

    Dung cho parallel processing - tranh lock contention.
    Caller chiu trach nhiem update cache sau.

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

        # Check cache truoc (read-only, khong can lock heavy)
        with _cache_lock:
            cached = _file_token_cache.get(path_str)
            if cached is not None:
                cached_mtime, cached_count = cached
                if cached_mtime == stat.st_mtime:
                    return cached_count

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
    global _file_token_cache

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
        with _cache_lock:
            cached = _file_token_cache.get(path_str)
            if cached is not None:
                cached_mtime, cached_count = cached
                if cached_mtime == stat.st_mtime:
                    # Move to end cho LRU
                    _file_token_cache.move_to_end(path_str)
                    return cached_count

        # Check binary su dung comprehensive detection
        from core.utils.file_utils import is_binary_file

        if is_binary_file(file_path):
            return 0

        # Doc va dem
        content = file_path.read_text(encoding="utf-8", errors="replace")
        token_count = count_tokens(content)

        # Update cache voi LRU eviction
        with _cache_lock:
            # Evict oldest neu at capacity
            while len(_file_token_cache) >= _MAX_CACHE_SIZE:
                _file_token_cache.popitem(last=False)  # Remove oldest

            _file_token_cache[path_str] = (stat.st_mtime, token_count)

        return token_count

    except (OSError, IOError):
        return 0


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================


def clear_token_cache():
    """Xoa toan bo file token cache."""
    global _file_token_cache
    _file_token_cache.clear()


def clear_file_from_cache(path: str):
    """
    Xoa cache entry cho mot file cu the.

    Goi khi file watcher phat hien file thay doi,
    de lan tinh token tiep theo se doc lai file.

    Args:
        path: Duong dan file can xoa khoi cache
    """
    global _file_token_cache
    _file_token_cache.pop(path, None)


# ============================================================================
# PARALLEL PROCESSING - Port from Repomix (src/shared/processConcurrency.ts)
# ============================================================================

# Worker initialization la expensive, nen dung it threads tru khi co nhieu files
TASKS_PER_WORKER = 100

# So file toi thieu de trigger parallel processing
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
    # ceil(num_tasks / TASKS_PER_WORKER)
    calculated = (num_tasks + TASKS_PER_WORKER - 1) // TASKS_PER_WORKER
    return max(1, min(cpu_count, calculated))


def count_tokens_batch(file_paths: List[Path]) -> Dict[str, int]:
    """
    Dem token cho nhieu files - SYNC version voi global cancellation.

    DEPRECATED: Dung count_tokens_batch_parallel() cho performance tot hon.
    Giu lai lam fallback neu parallel gap loi.

    Args:
        file_paths: Danh sach duong dan files can dem token.

    Returns:
        Dict mapping path string -> token count.
    """
    from services.token_display import is_counting_tokens

    results: Dict[str, int] = {}

    # Check cancellation truoc khi bat dau
    if not is_counting_tokens():
        return results

    for i, path in enumerate(file_paths):
        # Check global cancellation flag MOI file
        if not is_counting_tokens():
            return results

        try:
            results[str(path)] = count_tokens_for_file(path)
        except Exception:
            results[str(path)] = 0

        if i > 0 and i % 3 == 0 and not is_counting_tokens():
            return results

    return results


def count_tokens_batch_parallel(
    file_paths: List[Path],
    max_workers: int = 2,
    update_cache: bool = True,
) -> Dict[str, int]:
    """
    Dem token song song voi ThreadPoolExecutor + mmap.

    PERFORMANCE:
    - Claude models: Dung encode_batch() (Rust, 5-10x nhanh hon)
    - Other models: ThreadPoolExecutor (3-4x nhanh hon sequential)

    AN TOAN RACE CONDITION:
    - Moi file doc doc lap boi 1 worker
    - Khong update cache trong worker (tranh lock contention)
    - Collect results vao local dict
    - Update cache MOT LAN o cuoi voi lock

    Args:
        file_paths: Danh sach files can dem
        max_workers: So workers toi da (default 2)
        update_cache: Co update global cache khong

    Returns:
        Dict mapping path -> token count
    """
    from services.token_display import is_counting_tokens
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Check cancellation truoc
    if not is_counting_tokens():
        return {}

    if len(file_paths) == 0:
        return {}

    # Auto-detect: Neu model co tokenizer_repo, dung batch encoding (nhanh hon)
    tokenizer_repo = _get_tokenizer_repo()
    if tokenizer_repo and HAS_TOKENIZERS:
        return count_tokens_batch_hf(file_paths)

    # Standard parallel processing cho non-Claude models
    results: Dict[str, int] = {}
    file_mtimes: Dict[str, float] = {}  # De update cache sau

    # Gioi han workers theo so files
    num_workers = min(max_workers, len(file_paths), os.cpu_count() or 4)

    def count_single_file(path: Path) -> Tuple[str, int, float]:
        """
        Worker function - dem 1 file.

        Returns: (path_str, token_count, mtime)
        """
        # Check cancellation trong worker
        if not is_counting_tokens():
            return (str(path), 0, 0)

        try:
            # Skip binary files NGAY LAP TUC (truoc bat ky I/O nao)
            from core.utils.file_utils import is_binary_file

            if is_binary_file(path):
                return (str(path), 0, 0)

            stat = path.stat()
            count = _count_tokens_for_file_no_cache(path)
            return (str(path), count, stat.st_mtime)
        except Exception:
            return (str(path), 0, 0)

    try:
        # Parallel execution
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit tat ca tasks
            futures = {executor.submit(count_single_file, p): p for p in file_paths}

            # Collect results
            for future in as_completed(futures):
                # Check cancellation - cancel remaining neu can
                if not is_counting_tokens():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                try:
                    path_str, count, mtime = future.result(timeout=10)
                    results[path_str] = count
                    if mtime > 0:
                        file_mtimes[path_str] = mtime
                except Exception:
                    path = futures[future]
                    results[str(path)] = 0

        # Update cache MOT LAN (an toan, khong contention trong loop)
        if update_cache and results and is_counting_tokens():
            with _cache_lock:
                for path_str, count in results.items():
                    mtime = file_mtimes.get(path_str, 0)
                    if mtime > 0:
                        # Evict neu can
                        while len(_file_token_cache) >= _MAX_CACHE_SIZE:
                            _file_token_cache.popitem(last=False)
                        _file_token_cache[path_str] = (mtime, count)

    except Exception as e:
        # Fallback ve sequential neu parallel fail
        from core.logging_config import log_error

        log_error(
            f"[TokenCounter] Parallel counting failed: {e}, falling back to sequential"
        )
        return count_tokens_batch(file_paths)

    return results


def count_tokens_batch_hf(file_paths: List[Path]) -> Dict[str, int]:
    """
    Dem token cho models co tokenizer_repo su dung encode_batch() (Rust multi-thread).

    PERFORMANCE: Nhanh hon 5-10x so voi loop tung file.
    Su dung Rust backend cua tokenizers de xu ly batch cuc nhanh.

    Args:
        file_paths: Danh sach files can dem

    Returns:
        Dict mapping path -> token count
    """
    from services.token_display import is_counting_tokens

    if not is_counting_tokens():
        return {}

    if len(file_paths) == 0:
        return {}

    # Lay HF tokenizer
    tokenizer = _get_hf_tokenizer()
    if tokenizer is None:
        # Fallback to standard batch processing
        return count_tokens_batch_parallel(file_paths)

    results: Dict[str, int] = {}
    all_texts: List[str] = []
    valid_paths: List[str] = []

    # Doc tat ca files
    for path in file_paths:
        if not is_counting_tokens():
            return results

        try:
            # Check cache truoc
            stat = path.stat()
            mtime = stat.st_mtime
            path_str = str(path)

            with _cache_lock:
                if path_str in _file_token_cache:
                    cached_mtime, cached_count = _file_token_cache[path_str]
                    if cached_mtime == mtime:
                        results[path_str] = cached_count
                        continue

            # Doc file content
            content = _read_file_mmap(path)
            if content is None:
                results[path_str] = 0
                continue

            all_texts.append(content)
            valid_paths.append(path_str)

        except Exception:
            results[str(path)] = 0

    # Batch encode voi Rust backend (cuc nhanh!)
    if all_texts and is_counting_tokens():
        try:
            encodings = tokenizer.encode_batch(all_texts)

            # Extract token counts
            for path_str, encoding in zip(valid_paths, encodings):
                count = len(encoding.ids)
                results[path_str] = count

                # Update cache
                with _cache_lock:
                    path_obj = Path(path_str)
                    if path_obj.exists():
                        mtime = path_obj.stat().st_mtime
                        while len(_file_token_cache) >= _MAX_CACHE_SIZE:
                            _file_token_cache.popitem(last=False)
                        _file_token_cache[path_str] = (mtime, count)

        except Exception as e:
            from core.logging_config import log_error

            log_error(f"[TokenCounter] HF batch encoding failed: {e}")
            # Fallback to standard processing cho remaining files
            for path_str in valid_paths:
                if path_str not in results:
                    results[path_str] = 0

    return results
