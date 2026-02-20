"""
ITokenizationService - Interface cho dich vu dem token.

Dinh nghia contract ma bat ky TokenizationService nao cung phai tuan theo.
Cho phep dependency injection va testability (mock/stub).

Methods:
- count_tokens(): Dem token trong text
- count_tokens_for_file(): Dem token cho 1 file (co cache)
- count_tokens_batch_parallel(): Dem token song song nhieu files
- set_model_config(): Cap nhat cau hinh model/tokenizer
- reset_encoder(): Reset encoder khi user doi model
- clear_cache(): Xoa toan bo token cache
- clear_file_from_cache(): Xoa cache cho 1 file cu the
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional


class ITokenizationService(ABC):
    """
    Interface cho dich vu tokenization.

    Moi implementation phai dam bao:
    - Thread-safe cho moi operation
    - Khong su dung global mutable state
    - Fallback an toan khi encoder khong kha dung (Option 2b: warning + estimate)
    """

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Dem so token trong mot doan text.

        Neu encoder khong kha dung, fallback ve estimation
        va emit warning log (Option 2b).

        Args:
            text: Doan text can dem token

        Returns:
            So luong tokens (chinh xac hoac uoc luong)
        """
        ...

    @abstractmethod
    def count_tokens_for_file(self, file_path: Path) -> int:
        """
        Dem so token trong mot file voi LRU cache + mtime invalidation.

        Skip binary files va files qua lon (> 5MB).

        Args:
            file_path: Duong dan den file

        Returns:
            So luong tokens, hoac 0 neu skip/error
        """
        ...

    @abstractmethod
    def count_tokens_batch_parallel(
        self,
        file_paths: List[Path],
        max_workers: int = 2,
        update_cache: bool = True,
    ) -> Dict[str, int]:
        """
        Dem token song song cho nhieu files.

        Tu dong chon strategy phu hop:
        - HF encode_batch() cho models co tokenizer_repo
        - ThreadPoolExecutor cho cac models khac

        Args:
            file_paths: Danh sach file can dem
            max_workers: So workers toi da
            update_cache: Co update cache hay khong

        Returns:
            Dict mapping path string -> token count
        """
        ...

    @abstractmethod
    def set_model_config(self, tokenizer_repo: Optional[str] = None) -> None:
        """
        Cap nhat cau hinh tokenizer repo khi user doi model.

        Reset encoder hien tai va lazy-init encoder moi
        o lan count_tokens() tiep theo.

        Args:
            tokenizer_repo: HF repo ID (vd: "Xenova/claude-tokenizer") hoac None
        """
        ...

    @abstractmethod
    def reset_encoder(self) -> None:
        """
        Reset encoder instance hien tai.

        Goi khi can force reload encoder (vd: khi user doi model).
        """
        ...

    @abstractmethod
    def clear_cache(self) -> None:
        """Xoa toan bo file token cache."""
        ...

    @abstractmethod
    def clear_file_from_cache(self, path: str) -> None:
        """
        Xoa cache entry cho mot file cu the.

        Goi khi file watcher phat hien file thay doi.

        Args:
            path: Duong dan file can xoa khoi cache
        """
        ...
