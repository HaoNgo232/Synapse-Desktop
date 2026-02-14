"""
File Tree Filter Proxy - QSortFilterProxyModel cho search/filter.

Keeps parent folders visible nếu bất kỳ child nào match query.
Hiệu quả hơn so với manually tracking matched_paths.
"""

from PySide6.QtCore import QSortFilterProxyModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QWidget

from components.file_tree_model import FileTreeRoles


class FileTreeFilterProxy(QSortFilterProxyModel):
    """
    Filter tree items theo search query.
    
    Features:
    - Case-insensitive matching
    - Parent folders hiển thị nếu có descendant match
    - Tự động update khi filter text thay đổi
    """
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._search_query: str = ""
        self.setRecursiveFilteringEnabled(True)  # Qt 5.10+ auto-keeps ancestors
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    
    def set_search_query(self, query: str) -> None:
        """
        Set search query và trigger re-filter.
        
        Args:
            query: Search text (empty string = show all)
        """
        self._search_query = query.lower().strip()
        self.invalidateFilter()
    
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex) -> bool:
        """
        Filter logic: accept row nếu label chứa search query.
        
        Qt's recursiveFilteringEnabled=True tự động giữ parent folders
        nếu có descendant match.
        """
        if not self._search_query:
            return True
        
        index = self.sourceModel().index(source_row, 0, source_parent)
        if not index.isValid():
            return False
        
        # Check if label matches
        label = index.data(Qt.ItemDataRole.DisplayRole)
        if label and self._search_query in label.lower():
            return True
        
        # Check file path
        file_path = index.data(FileTreeRoles.FILE_PATH_ROLE)
        if file_path and self._search_query in file_path.lower():
            return True
        
        return False
    
    @property
    def search_query(self) -> str:
        return self._search_query
    
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
