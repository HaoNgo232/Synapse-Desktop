"""
TokenizationService - Concrete implementation cua ITokenizationService.

Thay the toan bo global state trong core/tokenization/counter.py va core/encoders.py.
Moi trang thai (encoder, tokenizer_repo, cache) duoc quan ly o instance level,
dam bao thread-safe va loai bo race conditions.
"""

import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from infrastructure.adapters.encoders import (
    HAS_TOKENIZERS,
    _estimate_tokens,
    _get_encoder,
    reset_encoder as _core_reset_encoder,
)
from shared.logging_config import log_info, log_warning
from domain.tokenization.cache import TokenCache
from domain.tokenization.cancellation import is_counting_tokens
from domain.ports.tokenization_port import ITokenizationService

from infrastructure.adapters.parallel_counter import (
    MAX_BYTES,
    count_tokens_for_file_no_cache,
    count_tokens_parallel_standard,
    count_tokens_batch_sequential,
    count_tokens_batch_hf,
)

# Worker config cho batch processing
TASKS_PER_WORKER = 100


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

        try:
            # Phân tách cách lấy base token count
            if getattr(self, "_encoder_type", "") == "hf":
                # HF tokenizer
                base_count = len(encoder.encode(text).ids)
            else:
                # rs-bpe va tiktoken
                base_count = len(encoder.encode(text))

            # --- DINH CHINH CLAUDE HEAVY WHITESPACE PENALTY ---
            if self._tokenizer_repo == "Xenova/claude-tokenizer":
                whitespace_count = text.count(" ") + text.count("\t") + text.count("\n")
                claude_corrected = int(base_count * 1.03) + int(whitespace_count * 0.25)
                return claude_corrected

            return base_count
        except Exception:
            # Fallback neu encode that bai
            return _estimate_tokens(text)

    def count_tokens_for_file(self, file_path: Path) -> int:
        """
        Dem so token trong file voi LRU cache + mtime invalidation.
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
            from shared.utils.file_utils import is_binary_file

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
        """
        if not is_counting_tokens() or len(file_paths) == 0:
            return {}

        # Auto-detect: model co tokenizer_repo -> dung batch encoding
        if self._tokenizer_repo and HAS_TOKENIZERS:
            return count_tokens_batch_hf(
                file_paths,
                self._tokenizer_repo,
                self._cache.get_no_move,
                self._cache.put_batch,
                self.count_tokens_batch_parallel,
            )

        # Standard parallel processing cho non-HF models
        return count_tokens_parallel_standard(
            file_paths,
            max_workers,
            update_cache,
            self._count_tokens_for_file_no_cache,
            self._cache.put_batch,
            self._count_tokens_batch_sequential,
        )

    def set_model_config(self, tokenizer_repo: Optional[str] = None) -> None:
        """
        Cap nhat cau hinh tokenizer repo khi user doi model.
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
        """
        self._cache.clear_file(path)

    # ================================================================
    # Internal / Private methods
    # ================================================================

    def _get_or_create_encoder(self) -> Optional[Any]:
        """
        Lay hoac khoi tao encoder (thread-safe lazy init).
        """
        if self._encoder is not None:
            return self._encoder

        with self._lock:
            if self._encoder is not None:
                return self._encoder

            encoder = _get_encoder(tokenizer_repo=self._tokenizer_repo)
            if encoder is not None:
                import infrastructure.adapters.encoders as _enc

                self._encoder_type = _enc._encoder_type
                self._using_estimation = False

            self._encoder = encoder
            return self._encoder

    def _count_tokens_for_file_no_cache(self, file_path: Path) -> int:
        """Dem token cho file KHONG update cache (parallel-safe)."""
        return count_tokens_for_file_no_cache(
            file_path, self._cache.get_no_move, self.count_tokens
        )

    def _count_tokens_batch_sequential(self, file_paths: List[Path]) -> Dict[str, int]:
        """Dem token tuan tu."""
        return count_tokens_batch_sequential(file_paths, self.count_tokens_for_file)

    @staticmethod
    def get_worker_count(num_tasks: int) -> int:
        """Tinh so luong workers toi uu."""
        cpu_count = os.cpu_count() or 4
        calculated = (num_tasks + TASKS_PER_WORKER - 1) // TASKS_PER_WORKER
        return max(1, min(cpu_count, calculated))
