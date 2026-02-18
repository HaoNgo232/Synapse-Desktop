"""
Batch/parallel token counting.

Functions:
- get_worker_count(): Tinh so workers toi uu
- count_tokens_batch(): Sequential batch (fallback)
- count_tokens_batch_parallel(): ThreadPoolExecutor batch
- count_tokens_batch_hf(): HF Rust encode_batch (cuc nhanh)

Port tu Repomix (src/shared/processConcurrency.ts).

DIP: Module nay KHONG import tu services layer.
Tokenizer repo duoc inject qua parameters.
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from core.encoders import HAS_TOKENIZERS
from core.tokenization.cancellation import is_counting_tokens
from core.tokenization.cache import token_cache
from core.tokenization.counter import (
    count_tokens_for_file,
    _count_tokens_for_file_no_cache,
    _read_file_mmap,
)

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
    tokenizer_repo: Optional[str] = None,
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
        tokenizer_repo: HF repo ID (inject tu caller)

    Returns:
        Dict mapping path -> token count
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Check cancellation truoc
    if not is_counting_tokens():
        return {}

    if len(file_paths) == 0:
        return {}

    # Auto-detect: Neu model co tokenizer_repo, dung batch encoding (nhanh hon)
    if tokenizer_repo and HAS_TOKENIZERS:
        return count_tokens_batch_hf(file_paths, tokenizer_repo)

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
            batch_entries = {
                path_str: (file_mtimes[path_str], count)
                for path_str, count in results.items()
                if path_str in file_mtimes and file_mtimes[path_str] > 0
            }
            if batch_entries:
                token_cache.put_batch(batch_entries)

    except Exception as e:
        # Fallback ve sequential neu parallel fail
        from core.logging_config import log_error

        log_error(
            f"[TokenCounter] Parallel counting failed: {e}, falling back to sequential"
        )
        return count_tokens_batch(file_paths)

    return results


def count_tokens_batch_hf(
    file_paths: List[Path], tokenizer_repo: Optional[str] = None
) -> Dict[str, int]:
    """
    Dem token cho models co tokenizer_repo su dung encode_batch() (Rust multi-thread).

    PERFORMANCE: Nhanh hon 5-10x so voi loop tung file.
    Su dung Rust backend cua tokenizers de xu ly batch cuc nhanh.

    Args:
        file_paths: Danh sach files can dem
        tokenizer_repo: HF repo ID (inject tu caller)

    Returns:
        Dict mapping path -> token count
    """
    if not is_counting_tokens():
        return {}

    if len(file_paths) == 0:
        return {}

    # Lay HF tokenizer
    from core.encoders import _get_hf_tokenizer

    tokenizer = _get_hf_tokenizer(tokenizer_repo)
    if tokenizer is None:
        # Fallback to standard batch processing
        return count_tokens_batch_parallel(file_paths, tokenizer_repo=tokenizer_repo)

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

            cached = token_cache.get_no_move(path_str, mtime)
            if cached is not None:
                results[path_str] = cached
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

            # Extract token counts va build batch entries
            batch_entries: Dict[str, Tuple[float, int]] = {}
            for path_str, encoding in zip(valid_paths, encodings):
                count = len(encoding.ids)
                results[path_str] = count

                # Prepare cache update
                try:
                    path_obj = Path(path_str)
                    if path_obj.exists():
                        mtime = path_obj.stat().st_mtime
                        batch_entries[path_str] = (mtime, count)
                except OSError:
                    pass

            # Update cache MOT LAN
            if batch_entries:
                token_cache.put_batch(batch_entries)

        except Exception as e:
            from core.logging_config import log_error

            log_error(f"[TokenCounter] HF batch encoding failed: {e}")
            # Fallback to standard processing cho remaining files
            for path_str in valid_paths:
                if path_str not in results:
                    results[path_str] = 0

    return results
