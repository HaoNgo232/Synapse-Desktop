"""
TokenizationService - Concrete implementation cua ITokenizationService.

Thay the toan bo global state trong core/tokenization/counter.py va core/encoders.py.
Moi trang thai (encoder, tokenizer_repo, cache) duoc quan ly o instance level,
dam bao thread-safe va loai bo race conditions.

Fallback Strategy (Option 2b):
  Khi encoder khong load duoc (offline, loi network), service se:
  1. Fallback ve _estimate_tokens() de ung dung khong bi gian doan
  2. Emit warning log de UI/developer biet rang dang dung gia tri uoc luong

Dependency Flow:
  encoder_registry -> TokenizationService -> domain.tokenization.counter (pure functions)
                                          -> domain.tokenization.cache (TokenCache)

Consolidation:
  Service delegates to domain/tokenization/counter.py for core counting logic.
  Service adds orchestration: encoder lifecycle, cache management, batch strategies,
  Claude-specific corrections.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.adapters.encoders import (
    HAS_TOKENIZERS,
    _estimate_tokens,
    _get_encoder,
    _get_hf_tokenizer,
    reset_encoder as _core_reset_encoder,
)
from shared.logging_config import log_error, log_info, log_warning
from domain.tokenization.cache import TokenCache
from domain.tokenization.cancellation import is_counting_tokens
from domain.tokenization.counter import (
    count_tokens as _core_count_tokens,
    _read_file_mmap,
    _count_tokens_for_file_no_cache as _core_count_file_no_cache,
    MAX_BYTES,
)
from application.interfaces.tokenization_port import ITokenizationService

# Worker config cho batch processing
TASKS_PER_WORKER = 100
MIN_FILES_FOR_PARALLEL = 10


class TokenizationService(ITokenizationService):
    """
    Dich vu dem token - thread-safe, khong dung global state.

    Quan ly encoder lifecycle va token cache trong instance scope.
    Ho tro nhieu loai encoder: rs-bpe, tiktoken, Hugging Face tokenizers.
    """

    def __init__(self, tokenizer_repo: Optional[str] = None) -> None:
        """
        Khoi tao TokenizationService.

        Args:
            tokenizer_repo: HF repo ID (vd: "Xenova/claude-tokenizer") hoac None
        """
        self._tokenizer_repo: Optional[str] = tokenizer_repo
        self._encoder: Optional[Any] = None
        self._encoder_type: str = ""
        self._lock = threading.RLock()
        self._cache = TokenCache()
        # Flag theo doi trang thai fallback (Option 2b)
        self._using_estimation = False

    # ================================================================
    # Public API - ITokenizationService contract
    # ================================================================

    def count_tokens(self, text: str) -> int:
        """
        Dem so token trong text.

        Delegates to domain.tokenization.counter.count_tokens() for base counting,
        then applies service-level corrections (e.g. Claude whitespace penalty).

        Args:
            text: Doan text can dem token

        Returns:
            So luong tokens
        """
        encoder = self._get_or_create_encoder()

        # Neu encoder khong kha dung, dung uoc luong va canh bao (Option 2b)
        if encoder is None:
            if not self._using_estimation:
                log_warning(
                    "[TokenizationService] Encoder khong kha dung, "
                    "dang su dung uoc luong (~4 ky tu/token). "
                    "Ket qua co the sai lech so voi thuc te."
                )
                self._using_estimation = True
            return _estimate_tokens(text)

        # Delegate base counting to domain counter pure function
        base_count = _core_count_tokens(
            text, encoder=encoder, encoder_type=self._encoder_type
        )

        # --- DINH CHINH CLAUDE HEAVY WHITESPACE PENALTY ---
        # Khi luong khoang trang nhiu, Claude tokenizer tokenization hieu qua rat thap
        if self._tokenizer_repo == "Xenova/claude-tokenizer":
            whitespace_count = text.count(" ") + text.count("\t") + text.count("\n")
            # Cong them 3% mac dinh va khoang 0.25 token cho moi whitespace/tab/newline
            claude_corrected = int(base_count * 1.03) + int(whitespace_count * 0.25)
            return claude_corrected

        return base_count

    def count_tokens_for_file(self, file_path: Path) -> int:
        """
        Dem so token trong file voi LRU cache + mtime invalidation.

        Skip binary files va files lon hon 5MB.

        Args:
            file_path: Duong dan den file

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

            # Check cache truoc (LRU management)
            cached = self._cache.get(path_str, stat.st_mtime)
            if cached is not None:
                return cached

            # Check binary file
            from infrastructure.filesystem.file_utils import is_binary_file

            if is_binary_file(file_path):
                return 0

            # Doc va dem
            content = file_path.read_text(encoding="utf-8", errors="replace")
            token_count = self.count_tokens(content)

            # Update cache
            self._cache.put(path_str, stat.st_mtime, token_count)
            return token_count

        except (OSError, IOError):
            return 0

    def count_tokens_batch_parallel(
        self,
        file_paths: List[Path],
        max_workers: int = 2,
        update_cache: bool = True,
    ) -> Dict[str, int]:
        """
        Dem token song song cho nhieu files.

        Tu dong chon strategy:
        - HF encode_batch() cho models co tokenizer_repo (5-10x nhanh)
        - ThreadPoolExecutor cho cac models khac (3-4x nhanh)

        Args:
            file_paths: Danh sach file can dem
            max_workers: So workers toi da
            update_cache: Co update cache hay khong

        Returns:
            Dict mapping path string -> token count
        """
        if not is_counting_tokens() or len(file_paths) == 0:
            return {}

        # Auto-detect: model co tokenizer_repo -> dung batch encoding (nhanh hon)
        if self._tokenizer_repo and HAS_TOKENIZERS:
            return self._count_tokens_batch_hf(file_paths)

        # Standard parallel processing cho non-HF models
        return self._count_tokens_parallel_standard(
            file_paths, max_workers, update_cache
        )

    def set_model_config(self, tokenizer_repo: Optional[str] = None) -> None:
        """
        Cap nhat cau hinh tokenizer repo khi user doi model.

        Reset encoder hien tai - encoder moi se duoc lazy-init
        o lan count_tokens() tiep theo.

        Args:
            tokenizer_repo: HF repo ID hoac None
        """
        with self._lock:
            self._tokenizer_repo = tokenizer_repo
            self._encoder = None
            self._encoder_type = ""
            self._using_estimation = False
        # Reset global encoder state trong core.encoders
        _core_reset_encoder()
        log_info(
            f"[TokenizationService] Model config updated: "
            f"tokenizer_repo={tokenizer_repo}"
        )

    def reset_encoder(self) -> None:
        """
        Reset encoder instance hien tai.

        Goi khi can force reload encoder.
        """
        with self._lock:
            self._encoder = None
            self._encoder_type = ""
            self._using_estimation = False
        _core_reset_encoder()
        log_info("[TokenizationService] Encoder reset - se reload lan goi tiep theo")

    def clear_cache(self) -> None:
        """Xoa toan bo file token cache."""
        self._cache.clear()

    def clear_file_from_cache(self, path: str) -> None:
        """
        Xoa cache entry cho mot file cu the.

        Args:
            path: Duong dan file can xoa khoi cache
        """
        self._cache.clear_file(path)

    # ================================================================
    # Internal / Private methods
    # ================================================================

    def _get_or_create_encoder(self) -> Optional[Any]:
        """
        Lay hoac khoi tao encoder (thread-safe lazy init).

        Returns:
            Encoder instance hoac None
        """
        # Fast path: encoder da khoi tao (khong can lock)
        if self._encoder is not None:
            return self._encoder

        # Thread-safe lazy initialization
        with self._lock:
            # Double-check sau khi lay lock
            if self._encoder is not None:
                return self._encoder

            self._encoder = _get_encoder(tokenizer_repo=self._tokenizer_repo)
            if self._encoder is not None:
                # Xac dinh loai encoder
                import infrastructure.adapters.encoders as _enc

                self._encoder_type = _enc._encoder_type
                self._using_estimation = False
            return self._encoder

    def _count_tokens_for_file_no_cache(self, file_path: Path) -> int:
        """
        Dem token cho file KHONG update cache (parallel-safe).

        Delegates to domain.tokenization.counter._count_tokens_for_file_no_cache().

        Args:
            file_path: Duong dan file

        Returns:
            So token hoac 0 neu khong dem duoc
        """
        encoder = self._get_or_create_encoder()
        if encoder is None:
            # Fallback level 2: Encoder None (Option 2b)
            try:
                if not file_path.exists() or not file_path.is_file():
                    return 0
                stat = file_path.stat()
                if stat.st_size > MAX_BYTES or stat.st_size == 0:
                    return 0
                content = file_path.read_text(encoding="utf-8", errors="replace")
                return _estimate_tokens(content)
            except Exception:
                return 0

        return _core_count_file_no_cache(
            file_path,
            encoder=encoder,
            encoder_type=self._encoder_type,
            cache=self._cache,
        )

    def _count_tokens_parallel_standard(
        self,
        file_paths: List[Path],
        max_workers: int,
        update_cache: bool,
    ) -> Dict[str, int]:
        """
        Dem token song song bang ThreadPoolExecutor.

        An toan race condition:
        - Moi worker doc file doc lap
        - Khong update cache trong worker (tranh lock contention)
        - Update cache MOT LAN o cuoi

        Args:
            file_paths: Danh sach files
            max_workers: So workers toi da
            update_cache: Co update cache khong

        Returns:
            Dict mapping path -> token count
        """
        results: Dict[str, int] = {}
        file_mtimes: Dict[str, float] = {}

        num_workers = min(max_workers, len(file_paths), os.cpu_count() or 4)

        def count_single_file(path: Path) -> Tuple[str, int, float]:
            """Worker function - dem 1 file."""
            if not is_counting_tokens():
                return (str(path), 0, 0)
            try:
                from infrastructure.filesystem.file_utils import is_binary_file

                if is_binary_file(path):
                    return (str(path), 0, 0)
                stat = path.stat()
                count = self._count_tokens_for_file_no_cache(path)
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
                    self._cache.put_batch(batch_entries)

        except Exception as e:
            log_error(
                f"[TokenizationService] Parallel counting failed: {e}, "
                f"falling back to sequential"
            )
            return self._count_tokens_batch_sequential(file_paths)

        return results

    def _count_tokens_batch_sequential(self, file_paths: List[Path]) -> Dict[str, int]:
        """
        Dem token tuan tu (fallback khi parallel that bai).

        Args:
            file_paths: Danh sach files

        Returns:
            Dict mapping path -> token count
        """
        results: Dict[str, int] = {}
        if not is_counting_tokens():
            return results

        for i, path in enumerate(file_paths):
            if not is_counting_tokens():
                return results
            try:
                results[str(path)] = self.count_tokens_for_file(path)
            except Exception:
                results[str(path)] = 0

            if i > 0 and i % 3 == 0 and not is_counting_tokens():
                return results

        return results

    def _count_tokens_batch_hf(self, file_paths: List[Path]) -> Dict[str, int]:
        """
        Dem token bang HF encode_batch() (Rust multi-thread, 5-10x nhanh).

        Args:
            file_paths: Danh sach files

        Returns:
            Dict mapping path -> token count
        """
        if not is_counting_tokens() or len(file_paths) == 0:
            return {}

        tokenizer = _get_hf_tokenizer(self._tokenizer_repo)
        if tokenizer is None:
            # Fallback to standard parallel khi HF tokenizer khong kha dung
            return self._count_tokens_parallel_standard(
                file_paths, max_workers=2, update_cache=True
            )

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

                cached = self._cache.get_no_move(path_str, stat.st_mtime)
                if cached is not None:
                    results[path_str] = cached
                    continue

                content = _read_file_mmap(path)
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
                    self._cache.put_batch(batch_entries)

            except Exception as e:
                log_error(f"[TokenizationService] HF batch encoding failed: {e}")
                for path_str in valid_paths:
                    if path_str not in results:
                        results[path_str] = 0

        return results

    @staticmethod
    def get_worker_count(num_tasks: int) -> int:
        """
        Tinh so luong workers toi uu.

        Args:
            num_tasks: So luong tasks can xu ly

        Returns:
            So luong workers toi uu
        """
        cpu_count = os.cpu_count() or 4
        calculated = (num_tasks + TASKS_PER_WORKER - 1) // TASKS_PER_WORKER
        return max(1, min(cpu_count, calculated))
