"""
Ignore Strategies cho File Watcher.

Chua cac implementation cua IIgnoreStrategy:
- DefaultIgnoreStrategy: Bo qua cac thu muc pho bien (.git, node_modules, ...)

Mo rong trong tuong lai:
- GitIgnoreStrategy: Doc .gitignore de xac dinh bo qua
- CompositeIgnoreStrategy: Ket hop nhieu strategies
"""

from pathlib import Path
from typing import Set

from services.interfaces.file_watcher_service import IIgnoreStrategy


class DefaultIgnoreStrategy(IIgnoreStrategy):
    """
    Ignore strategy mac dinh - bo qua cac thu muc pho bien.

    Su dung hardcoded patterns cho cac thu muc khong can theo doi
    nhu .git, node_modules, __pycache__, v.v.

    Attributes:
        IGNORED_PATTERNS: Set cac ten thu muc can bo qua
    """

    # Danh sach patterns can ignore (hardcoded de don gian)
    IGNORED_PATTERNS: Set[str] = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
        ".idea",
        ".vscode",
        "dist",
        "build",
        ".mypy_cache",
    }

    def should_ignore(self, path: str) -> bool:
        """
        Kiem tra path co nam trong thu muc can bo qua khong.

        Duyet tung phan cua path va so sanh voi IGNORED_PATTERNS.

        Args:
            path: Duong dan tuyet doi can kiem tra

        Returns:
            True neu bat ky phan nao cua path nam trong IGNORED_PATTERNS
        """
        path_parts = Path(path).parts
        for pattern in self.IGNORED_PATTERNS:
            if pattern in path_parts:
                return True
        return False
