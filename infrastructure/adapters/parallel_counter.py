import mmap
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared.logging_config import log_error
from domain.tokenization.cancellation import is_counting_tokens

MAX_BYTES = 5 * 1024 * 1024


def read_file_mmap(file_path: Path) -> Optional[str]:
    """Doc file su dung mmap - nhanh hon read() thong thuong.

    mmap map file truc tiep vao virtual memory,
    giam so lan copy data giua kernel va user space.
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


def count_tokens_for_file_no_cache(
    file_path: Path,
    cache_get_no_move_func: Callable[[str, float], Optional[int]],
    count_tokens_func: Callable[[str], int],
) -> int:
    """Dem token cho file KHONG update cache (parallel-safe).

    Caller chiu trach nhiem update cache sau.
    """
    try:
        if not file_path.exists() or not file_path.is_file():
            return 0

        stat = file_path.stat()
        if stat.st_size > MAX_BYTES or stat.st_size == 0:
            return 0

        path_str = str(file_path)

        # Check cache truoc (read-only, khong move LRU)
        cached = cache_get_no_move_func(path_str, stat.st_mtime)
        if cached is not None:
            return cached

        from shared.utils.file_utils import is_binary_file

        if is_binary_file(file_path):
            return 0

        content = read_file_mmap(file_path)
        if content is None:
            return 0

        return count_tokens_func(content)

    except Exception:
        return 0


def count_tokens_parallel_standard(
    file_paths: List[Path],
    max_workers: int,
    update_cache: bool,
    count_tokens_for_file_no_cache_func: Callable[[Path], int],
    cache_put_batch_func: Callable[[Dict[str, Tuple[float, int]]], None],
    fallback_func: Callable[[List[Path]], Dict[str, int]],
) -> Dict[str, int]:
    """Dem token song song bang ThreadPoolExecutor."""
    results: Dict[str, int] = {}
    file_mtimes: Dict[str, float] = {}

    num_workers = min(max_workers, len(file_paths), os.cpu_count() or 4)

    def count_single_file(path: Path) -> Tuple[str, int, float]:
        """Worker function - dem 1 file."""
        if not is_counting_tokens():
            return (str(path), 0, 0)
        try:
            from shared.utils.file_utils import is_binary_file

            if is_binary_file(path):
                return (str(path), 0, 0)
            stat = path.stat()
            count = count_tokens_for_file_no_cache_func(path)
            return (str(path), count, stat.st_mtime)
        except Exception:
            return (str(path), 0, 0)

    try:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(count_single_file, p): p for p in file_paths}
            for future in as_completed(futures):
                if not is_counting_tokens():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    path_str, count, mtime_val = future.result(timeout=10)
                    results[path_str] = count
                    if mtime_val > 0:
                        file_mtimes[path_str] = mtime_val
                except Exception:
                    path = futures[future]
                    results[str(path)] = 0

        # Update cache MOT LAN (an toan, khong contention)
        if update_cache and results and is_counting_tokens():
            batch_entries = {
                path_str: (file_mtimes[path_str], count)
                for path_str, count in results.items()
                if path_str in file_mtimes and file_mtimes[path_str] > 0
            }
            if batch_entries:
                cache_put_batch_func(batch_entries)

    except Exception as e:
        log_error(
            f"[TokenizationService] Parallel counting failed: {e}, "
            f"falling back to sequential"
        )
        return fallback_func(file_paths)

    return results


def count_tokens_batch_sequential(
    file_paths: List[Path],
    count_tokens_for_file_func: Callable[[Path], int],
) -> Dict[str, int]:
    """Dem token tuan tu (fallback khi parallel that bai)."""
    results: Dict[str, int] = {}
    if not is_counting_tokens():
        return results

    for i, path in enumerate(file_paths):
        if not is_counting_tokens():
            return results
        try:
            results[str(path)] = count_tokens_for_file_func(path)
        except Exception:
            results[str(path)] = 0

        if i > 0 and i % 3 == 0 and not is_counting_tokens():
            return results

    return results


def count_tokens_batch_hf(
    file_paths: List[Path],
    tokenizer_repo: Optional[str],
    cache_get_no_move_func: Callable[[str, float], Optional[int]],
    cache_put_batch_func: Callable[[Dict[str, Tuple[float, int]]], None],
    fallback_parallel_func: Callable[[List[Path], int, bool], Dict[str, int]],
) -> Dict[str, int]:
    """Dem token bang HF encode_batch() (Rust multi-thread, 5-10x nhanh)."""
    from infrastructure.adapters.encoders import _get_hf_tokenizer

    if not is_counting_tokens() or len(file_paths) == 0:
        return {}

    tokenizer = _get_hf_tokenizer(tokenizer_repo)
    if tokenizer is None:
        # Fallback to standard parallel khi HF tokenizer khong kha dung
        return fallback_parallel_func(file_paths, 2, True)

    results: Dict[str, int] = {}
    all_texts: List[str] = []
    valid_paths: List[str] = []

    # Doc tat ca files
    for path in file_paths:
        if not is_counting_tokens():
            return results
        try:
            stat = path.stat()
            path_str = str(path)

            cached = cache_get_no_move_func(path_str, stat.st_mtime)
            if cached is not None:
                results[path_str] = cached
                continue

            content = read_file_mmap(path)
            if content is None:
                results[path_str] = 0
                continue

            all_texts.append(content)
            valid_paths.append(path_str)
        except Exception:
            results[str(path)] = 0

    # Batch encode voi Rust backend
    if all_texts and is_counting_tokens():
        try:
            encodings = tokenizer.encode_batch(all_texts)
            batch_entries: Dict[str, Tuple[float, int]] = {}

            for path_str, encoding in zip(valid_paths, encodings):
                count = len(encoding.ids)
                results[path_str] = count
                try:
                    path_obj = Path(path_str)
                    if path_obj.exists():
                        mtime_val = path_obj.stat().st_mtime
                        batch_entries[path_str] = (mtime_val, count)
                except OSError:
                    pass

            if batch_entries:
                cache_put_batch_func(batch_entries)

        except Exception as e:
            log_error(f"[TokenizationService] HF batch encoding failed: {e}")
            for path_str in valid_paths:
                if path_str not in results:
                    results[path_str] = 0

    return results
