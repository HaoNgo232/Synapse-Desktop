"""
Token Counter - Thin adapter cho core.tokenization package.

Backward-compatible public API. Tat ca logic da chuyen sang:
- core.tokenization.counter: Core counting (text + file)
- core.tokenization.batch: Parallel/batch processing
- core.tokenization.cache: LRU cache voi mtime invalidation
- core.tokenization.cancellation: Thread-safe cancellation flag

Giu lai file nay de:
1. Backward compat - tat ca consumers import tu day
2. Re-export reset_encoder tu core.encoders
"""

# Re-export core counting functions
from core.tokenization.counter import (  # noqa: F401
    count_tokens,
    count_tokens_for_file,
    _count_tokens_for_file_no_cache,
    _read_file_mmap,
    MAX_BYTES,
)

# Re-export batch processing functions
from core.tokenization.batch import (  # noqa: F401
    get_worker_count,
    count_tokens_batch,
    count_tokens_batch_parallel,
    count_tokens_batch_hf,
    TASKS_PER_WORKER,
    MIN_FILES_FOR_PARALLEL,
)

# Re-export cache management (delegate to TokenCache singleton)
from core.tokenization.cache import token_cache as _token_cache


def clear_token_cache():
    """Xoa toan bo file token cache."""
    _token_cache.clear()


def clear_file_from_cache(path: str):
    """
    Xoa cache entry cho mot file cu the.

    Goi khi file watcher phat hien file thay doi,
    de lan tinh token tiep theo se doc lai file.

    Args:
        path: Duong dan file can xoa khoi cache
    """
    _token_cache.clear_file(path)


# Re-export encoder management (backward compat)
from core.encoders import reset_encoder  # noqa: F401, E402
