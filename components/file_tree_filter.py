"""
File Tree Filter Proxy - QSortFilterProxyModel cho search/filter.

Keeps parent folders visible nếu bất kỳ child nào match query.
Hiệu quả hơn so với manually tracking matched_paths.

Hỗ trợ 2 chế độ filter:
- Tên file (mặc định): filter theo label/path chứa query
- Nội dung file (prefix "code:"): filter theo danh sách file đã match content
"""

from typing import Optional, Set

from PySide6.QtCore import QSortFilterProxyModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QWidget

from components.file_tree_model import FileTreeRoles

# Prefix dùng để kích hoạt chế độ tìm kiếm nội dung file
CODE_SEARCH_PREFIX = "code:"


class FileTreeFilterProxy(QSortFilterProxyModel):
    """
    Filter tree items theo search query.

    Features:
    - Case-insensitive matching
    - Parent folders hiển thị nếu có descendant match
    - Tự động update khi filter text thay đổi
    - Hỗ trợ filter theo nội dung file (prefix "code:")
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._search_query: str = ""
        self._is_content_search: bool = False

        # Tập đường dẫn các file đã được flat index match (áp dụng cho CẢ mảng content lẫn file name)
        self._matched_paths: Optional[Set[str]] = None
        self._matched_ancestors: Set[str] = set()

        self.setRecursiveFilteringEnabled(True)  # Qt 5.10+ auto-keeps ancestors
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_search_state(self, query: str, matched_paths: Optional[Set[str]]) -> None:
        """
        Set search query cùng danh sách các đường dẫn đã match từ flat index.
        Sử dụng O(1) Ancestors Lookup để ngăn chặn lọt sỗ folder chưa lazy-load.

        Args:
            query: Cụm từ tìm kiếm
            matched_paths: Set tất cả file paths từ flat search.
        """
        stripped = query.strip()
        if stripped.lower().startswith(CODE_SEARCH_PREFIX):
            self._search_query = stripped[len(CODE_SEARCH_PREFIX) :].strip().lower()
            self._is_content_search = True
        else:
            self._search_query = stripped.lower()
            self._is_content_search = False

        self._matched_paths = matched_paths
        self._matched_ancestors = set()

        if matched_paths is not None:
            import os

            for p in matched_paths:
                # Build all valid ancestor prefixes for fast O(1) folder checking
                curr = os.path.dirname(p)
                # Keep climbing up until root
                while curr and curr != "/" and curr not in self._matched_ancestors:
                    self._matched_ancestors.add(curr)
                    next_curr = os.path.dirname(curr)
                    if next_curr == curr:  # Reached root (e.g. '/' or 'C:\')
                        break
                    curr = next_curr

        self.invalidateFilter()

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        """
        Filter logic:
        Sử dụng thuật toán O(1) Ancestors Lookup cho phép folder trống (lazy-loaded)
        nằm trong đường dẫn của result pass file check.
        """
        if not self._search_query:
            return True

        index = self.sourceModel().index(source_row, 0, source_parent)
        if not index.isValid():
            return False

        file_path = index.data(FileTreeRoles.FILE_PATH_ROLE)
        is_dir = index.data(FileTreeRoles.IS_DIR_ROLE)

        if not file_path:
            return False

        if is_dir:
            # Thuật toán chung: O(1) check tổ tiên của 1 file nào đó match
            if self._matched_ancestors and file_path in self._matched_ancestors:
                return True

            # Nếu ko phải content search, folder name có thể đang được trực tiếp search bằng string matching
            if not self._is_content_search:
                label = index.data(Qt.ItemDataRole.DisplayRole)
                if label and self._search_query in label.lower():
                    return True
                if self._search_query in file_path.lower():
                    return True
            return False

        # File
        # Fallback vào match set (vì file lazy load cũng check logic này)
        if self._matched_paths is not None:
            if file_path in self._matched_paths:
                return True
            return False

        # Mode mặc định cực phụ fallback khi chưa set map string-matching
        if not self._is_content_search:
            label = index.data(Qt.ItemDataRole.DisplayRole)
            if label and self._search_query in label.lower():
                return True
            if self._search_query in file_path.lower():
                return True

        return False

    @property
    def search_query(self) -> str:
        return self._search_query

    @property
    def is_content_search(self) -> bool:
        """Kiểm tra có đang ở chế độ tìm kiếm nội dung không."""
        return self._is_content_search

    def get_match_count(self) -> int:
        """Đếm số items matching filter."""
        return self._count_visible_items(QModelIndex())

    def _count_visible_items(self, parent: QModelIndex) -> int:
        """Recursively đếm visible items."""
        count = 0
        for row in range(self.rowCount(parent)):
            index = self.index(row, 0, parent)
            if index.isValid():
                # Chỉ đếm items thật sự match (không phải parent containers)
                is_dir = index.data(FileTreeRoles.IS_DIR_ROLE)
                if not is_dir:
                    count += 1
                count += self._count_visible_items(index)
        return count
