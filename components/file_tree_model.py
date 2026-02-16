"""
File Tree Model - QAbstractItemModel cho file tree với lazy loading.

KEY OPTIMIZATIONS:
1. Lazy loading: Chỉ load children khi parent được expand (canFetchMore/fetchMore)
2. No widget creation per row — Qt model/view pattern chỉ paint visible rows
3. Incremental updates: beginInsertRows/endInsertRows cho surgical updates
4. Role-based data: Token counts, line counts, selection state stored as custom roles
5. O(1) path lookup thông qua _path_to_index dictionary
"""

import logging
import os
import threading
from pathlib import Path
from typing import Optional, Set, Dict, List, Any

from PySide6.QtCore import (
    QAbstractItemModel, QModelIndex, QPersistentModelIndex, Qt, Signal, QObject, QRunnable, Slot,
)

from core.utils.file_utils import TreeItem, scan_directory_shallow

logger = logging.getLogger(__name__)


class TreeNode:
    """
    Internal node cho file tree model.
    
    Wraps TreeItem từ core/utils/file_utils.py
    và thêm Qt-specific state (parent tracking, row index).
    """
    
    __slots__ = (
        'label', 'path', 'is_dir', 'is_loaded',
        'children', 'parent', 'row',
    )
    
    def __init__(
        self,
        label: str,
        path: str,
        is_dir: bool = False,
        is_loaded: bool = False,
        parent: Optional['TreeNode'] = None,
        row: int = 0,
    ):
        self.label = label
        self.path = path
        self.is_dir = is_dir
        self.is_loaded = is_loaded  # True = children đã scan
        self.children: List['TreeNode'] = []
        self.parent = parent
        self.row = row
    
    def child_count(self) -> int:
        return len(self.children)
    
    def child(self, row: int) -> Optional['TreeNode']:
        if 0 <= row < len(self.children):
            return self.children[row]
        return None
    
    @staticmethod
    def from_tree_item(
        item: TreeItem,
        parent: Optional['TreeNode'] = None,
        row: int = 0,
        depth: int = 0,
        max_depth: int = 1,
    ) -> 'TreeNode':
        """
        Chuyển đổi TreeItem sang TreeNode (recursive, depth-limited).
        
        Args:
            item: TreeItem từ file_utils
            parent: Parent TreeNode
            row: Row index trong parent
            depth: Depth hiện tại
            max_depth: Depth tối đa để load children
        """
        node = TreeNode(
            label=item.label,
            path=item.path,
            is_dir=item.is_dir,
            is_loaded=not item.is_dir or depth < max_depth,
            parent=parent,
            row=row,
        )
        
        # Load children nếu trong depth limit
        if item.is_dir and depth < max_depth:
            for i, child_item in enumerate(item.children):
                child_node = TreeNode.from_tree_item(
                    child_item, parent=node, row=i,
                    depth=depth + 1, max_depth=max_depth,
                )
                node.children.append(child_node)
        
        return node


# Custom roles cho data
class FileTreeRoles:
    TOKEN_COUNT_ROLE = Qt.ItemDataRole.UserRole + 1
    LINE_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
    IS_SELECTED_ROLE = Qt.ItemDataRole.UserRole + 3
    FILE_PATH_ROLE = Qt.ItemDataRole.UserRole + 4
    IS_DIR_ROLE = Qt.ItemDataRole.UserRole + 5
    IS_LOADED_ROLE = Qt.ItemDataRole.UserRole + 6


class FileTreeModel(QAbstractItemModel):
    """
    Custom model cho file tree.
    
    Features:
    - Lazy loading via canFetchMore/fetchMore
    - Checkbox tri-state selection
    - Token/line count via custom roles
    - Background token counting
    - Path-based O(1) index lookup
    """
    
    # Signals
    selection_changed = Signal(set)  # Set[str] - selected file paths
    token_count_updated = Signal(str, int)  # (path, count)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._root_node: Optional[TreeNode] = None
        self._invisible_root = TreeNode("", "", is_dir=True, is_loaded=True)
        
        # Selection state
        self._selected_paths: Set[str] = set()
        
        # Token cache
        self._token_cache: Dict[str, int] = {}
        
        # Line count cache  
        self._line_cache: Dict[str, int] = {}

        # Folder check state cache
        self._folder_state_cache: Dict[str, Qt.CheckState] = {}
        
        # Path -> QModelIndex mapping cho O(1) lookup
        self._path_to_node: Dict[str, TreeNode] = {}
        
        # Last resolved file paths (set by token counting to track deep files)
        self._last_resolved_files: Set[str] = set()
        
        # Workspace root
        self._workspace_path: Optional[Path] = None
        
        # Original TreeItem root (for tree map generation)
        self._root_tree_item: Optional[TreeItem] = None
        
        # Generation counter — incremented on load_tree() to invalidate stale workers
        self._generation: int = 0
        self._generation_lock = threading.Lock()
        
        # Flat search index: maps lowercase filename -> list of full paths
        # Built via os.walk in background, independent of lazy tree loading
        self._search_index: Dict[str, List[str]] = {}
        self._search_index_ready = False
    
    # ===== QAbstractItemModel Interface =====
    
    def index(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        
        parent_node = parent.internalPointer() if parent.isValid() else self._get_root_parent()
        
        child = parent_node.child(row)
        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()
    
    def parent(self, index: QModelIndex | QPersistentModelIndex = QModelIndex()) -> QModelIndex:  # type: ignore[override]
        if not index.isValid():
            return QModelIndex()
        
        node: TreeNode = index.internalPointer()
        parent_node = node.parent
        
        if parent_node is None or parent_node is self._get_root_parent():
            return QModelIndex()
        
        return self.createIndex(parent_node.row, 0, parent_node)
    
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        if parent.column() > 0:
            return 0
        
        parent_node = parent.internalPointer() if parent.isValid() else self._get_root_parent()
        return parent_node.child_count()
    
    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 1
    
    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        
        node: TreeNode = index.internalPointer()
        
        if role == Qt.ItemDataRole.DisplayRole:
            return node.label
        
        elif role == Qt.ItemDataRole.CheckStateRole:
            if node.is_dir:
                # Tri-state cho folders
                return self._get_folder_check_state(node)
            return Qt.CheckState.Checked if node.path in self._selected_paths else Qt.CheckState.Unchecked
        
        elif role == FileTreeRoles.TOKEN_COUNT_ROLE:
            if node.is_dir:
                return self._get_folder_token_total(node)
            return self._token_cache.get(node.path)
        
        elif role == FileTreeRoles.LINE_COUNT_ROLE:
            return self._line_cache.get(node.path)
        
        elif role == FileTreeRoles.IS_SELECTED_ROLE:
            return node.path in self._selected_paths
        
        elif role == FileTreeRoles.FILE_PATH_ROLE:
            return node.path
        
        elif role == FileTreeRoles.IS_DIR_ROLE:
            return node.is_dir
        
        elif role == FileTreeRoles.IS_LOADED_ROLE:
            return node.is_loaded
        
        elif role == Qt.ItemDataRole.ToolTipRole:
            return node.path
        
        return None
    
    def setData(self, index: QModelIndex | QPersistentModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        
        if role == Qt.ItemDataRole.CheckStateRole:
            node: TreeNode = index.internalPointer()
            
            if value == Qt.CheckState.Checked:
                self._select_node(node)
            else:
                self._deselect_node(node)

            self._clear_folder_state_cache()
            self._emit_tree_checkstate_changed()
            self.selection_changed.emit(set(self._selected_paths))
            return True
        
        return False
    
    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag(0)
        
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
        return flags
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return "Files"
        return None
    
    # ===== Lazy Loading =====
    
    def canFetchMore(self, parent: QModelIndex | QPersistentModelIndex) -> bool:
        """Return True nếu folder chưa load children (lazy loading)."""
        if not parent.isValid():
            return False
        node: TreeNode = parent.internalPointer()
        return node.is_dir and not node.is_loaded
    
    def fetchMore(self, parent: QModelIndex | QPersistentModelIndex) -> None:
        """Load children on-demand khi user expand folder."""
        if not parent.isValid():
            return
        
        node: TreeNode = parent.internalPointer()
        if not node.is_dir or node.is_loaded:
            return
        
        # Load children từ filesystem
        folder_path = Path(node.path)
        if not folder_path.exists():
            node.is_loaded = True
            return
        
        try:
            from core.utils.file_utils import load_folder_children, TreeItem as _TreeItem
            from views.settings_view_qt import get_excluded_patterns, get_use_gitignore
            
            # Build a temporary TreeItem to use with load_folder_children
            temp_item = _TreeItem(
                label=node.label,
                path=node.path,
                is_dir=True,
                is_loaded=False,
                children=[],
            )
            load_folder_children(
                temp_item,
                excluded_patterns=get_excluded_patterns(),
                use_gitignore=get_use_gitignore(),
            )
            children_items = temp_item.children
        except Exception as e:
            logger.error(f"Error loading children for {node.path}: {e}")
            node.is_loaded = True
            return
        
        if not children_items:
            node.is_loaded = True
            return
        
        # Insert children vào model
        self.beginInsertRows(parent, 0, len(children_items) - 1)
        
        added_selected = False
        for i, child_item in enumerate(children_items):
            child_node = TreeNode(
                label=child_item.label,
                path=child_item.path,
                is_dir=child_item.is_dir,
                is_loaded=not child_item.is_dir,  # Files are always "loaded"
                parent=node,
                row=i,
            )
            node.children.append(child_node)
            self._path_to_node[child_node.path] = child_node
            
            # Nếu parent đang selected, auto-select children
            if node.path in self._selected_paths:
                self._selected_paths.add(child_node.path)
                added_selected = True
        
        node.is_loaded = True
        self.endInsertRows()

        if added_selected:
            self._clear_folder_state_cache()
            self._emit_tree_checkstate_changed()
            self.selection_changed.emit(set(self._selected_paths))
    
    def hasChildren(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        """Folders luôn return True để hiện expand arrow."""
        if not parent.isValid():
            return self._get_root_parent().child_count() > 0
        node: TreeNode = parent.internalPointer()
        if node.is_dir and not node.is_loaded:
            return True  # Giả sử folder có children cho đến khi load
        return node.child_count() > 0
    
    # ===== Public API =====
    
    def load_tree(self, workspace_path: Path) -> None:
        """
        Load file tree cho workspace mới.
        
        Dùng scan_directory_shallow(depth=1) để load nhanh.
        Children sâu hơn sẽ được lazy-load khi expand.
        """
        self._workspace_path = workspace_path
        
        # Increment generation to invalidate in-flight background workers
        with self._generation_lock:
            self._generation += 1
        
        self.beginResetModel()
        
        self._selected_paths.clear()
        self._token_cache.clear()
        self._line_cache.clear()
        self._path_to_node.clear()
        self._folder_state_cache.clear()
        self._last_resolved_files.clear()
        self._search_index.clear()
        self._search_index_ready = False
        
        try:
            # Get excluded patterns from settings
            from views.settings_view_qt import get_excluded_patterns
            excluded = get_excluded_patterns()
            
            tree_item = scan_directory_shallow(
                workspace_path, 
                depth=1,
                excluded_patterns=excluded if excluded else None
            )
            if tree_item:
                self._root_tree_item = tree_item
                self._root_node = TreeNode.from_tree_item(
                    tree_item, parent=self._invisible_root, row=0,
                    depth=0, max_depth=1,
                )
                self._invisible_root.children = [self._root_node]
                self._build_path_index(self._root_node)
            else:
                self._root_node = None
                self._invisible_root.children = []
        except Exception as e:
            logger.error(f"Error loading tree: {e}")
            self._root_node = None
            self._invisible_root.children = []
        
        self.endResetModel()
        
        # Build flat search index in background (independent of lazy loading)
        if workspace_path.exists():
            self._build_search_index_async(workspace_path)
    
    def get_selected_paths(self) -> List[str]:
        """
        Get danh sách selected file paths (chỉ files, không folders).
        
        Nếu có folder được selected mà children chưa loaded (lazy loading),
        sẽ scan filesystem trực tiếp để tìm tất cả files bên trong.
        Đảm bảo token counting luôn đầy đủ dù tree chưa expand.
        Skip binary/image files.
        """
        from core.utils.file_utils import is_binary_file
        
        result: List[str] = []
        seen: Set[str] = set()
        
        for p in self._selected_paths:
            node = self._path_to_node.get(p)
            if node is not None:
                if not node.is_dir:
                    if p not in seen and not is_binary_file(Path(p)):
                        result.append(p)
                        seen.add(p)
                elif node.is_dir:
                    # Folder selected — collect all files recursively
                    self._collect_files_deep(node, result, seen)
            else:
                # Path in selected but not in model (e.g. deep unloaded file)
                path_obj = Path(p)
                if path_obj.is_file() and p not in seen and not is_binary_file(path_obj):
                    result.append(p)
                    seen.add(p)
                elif path_obj.is_dir():
                    self._collect_files_from_disk(path_obj, result, seen)
        
        return result
    
    def _collect_files_deep(self, node: TreeNode, result: List[str], seen: Set[str]) -> None:
        """
        Collect tất cả files từ node. Nếu subfolder chưa loaded,
        scan filesystem trực tiếp thay vì bỏ qua.
        Skip binary/image files.
        """
        from core.utils.file_utils import is_binary_file
        
        for child in node.children:
            if child.path in seen:
                continue
            if not child.is_dir:
                if not is_binary_file(Path(child.path)):
                    result.append(child.path)
                    seen.add(child.path)
            elif child.is_dir:
                if child.is_loaded:
                    self._collect_files_deep(child, result, seen)
                else:
                    # Chưa loaded — scan disk trực tiếp
                    self._collect_files_from_disk(Path(child.path), result, seen)
        
        # Nếu folder chưa loaded và ko có children
        if node.is_dir and not node.is_loaded and not node.children:
            self._collect_files_from_disk(Path(node.path), result, seen)
    
    def _collect_files_from_disk(self, folder: Path, result: List[str], seen: Set[str]) -> None:
        """
        Scan filesystem trực tiếp để tìm tất cả files trong folder.
        Dùng cho folders chưa lazy-loaded trong tree model.
        Respect excluded patterns, gitignore, và binary extensions.
        """
        from core.utils.file_utils import (
            is_binary_file, is_system_path,
            get_cached_pathspec, _read_gitignore,
        )
        from core.constants import EXTENDED_IGNORE_PATTERNS
        from views.settings_view_qt import get_excluded_patterns, get_use_gitignore
        
        # Build ignore spec giống load_folder_children
        ignore_patterns: List[str] = [".git", ".hg", ".svn"]
        ignore_patterns.extend(EXTENDED_IGNORE_PATTERNS)
        
        excluded = get_excluded_patterns()
        if excluded:
            ignore_patterns.extend(excluded)
        
        # Tìm git root
        root_path = folder
        while root_path.parent != root_path:
            if (root_path / ".git").exists():
                break
            root_path = root_path.parent
        
        # Fallback to workspace root nếu có
        if self._workspace_path and self._workspace_path != root_path:
            ws = self._workspace_path
            while ws.parent != ws:
                if (ws / ".git").exists():
                    root_path = ws
                    break
                ws = ws.parent
        
        if get_use_gitignore():
            gitignore_patterns = _read_gitignore(root_path)
            ignore_patterns.extend(gitignore_patterns)
        
        spec = get_cached_pathspec(root_path, list(ignore_patterns))
        
        from core.constants import DIRECTORY_QUICK_SKIP
        
        root_path_str = str(root_path)
        
        try:
            for dirpath, dirnames, filenames in os.walk(str(folder)):
                # Prune ignored directories IN-PLACE — os.walk sẽ KHÔNG enter vào
                # Đây là key fix: tránh traverse node_modules (100K+ files)
                dirnames[:] = sorted(d for d in dirnames if d not in DIRECTORY_QUICK_SKIP)
                
                for filename in filenames:
                    full_path = os.path.join(dirpath, filename)
                    entry = Path(full_path)
                    
                    if is_system_path(entry) or is_binary_file(entry):
                        continue
                    
                    # Check pathspec
                    try:
                        rel_path_str = os.path.relpath(full_path, root_path_str)
                    except ValueError:
                        rel_path_str = filename
                    
                    if spec.match_file(rel_path_str):
                        continue
                    
                    if full_path not in seen:
                        result.append(full_path)
                        seen.add(full_path)
        except (PermissionError, OSError) as e:
            logger.debug(f"Error scanning {folder}: {e}")
    
    def get_root_tree_item(self) -> Optional[TreeItem]:
        """Get root TreeItem (for tree map generation)."""
        return self._root_tree_item
    
    def get_all_selected_paths(self) -> Set[str]:
        """Get tất cả selected paths (cả files và folders)."""
        return set(self._selected_paths)
    
    def get_expanded_paths(self) -> List[str]:
        """Get danh sách expanded folder paths. Cần TreeView reference."""
        # Sẽ được gọi từ bên ngoài với TreeView access
        return []
    
    def set_selected_paths(self, paths: Set[str]) -> None:
        """Set selected paths (cho session restore)."""
        self._selected_paths = set(paths)
        self._clear_folder_state_cache()
        self._emit_tree_checkstate_changed()
        self.selection_changed.emit(set(self._selected_paths))
    
    def add_paths_to_selection(self, paths: Set[str]) -> int:
        """Add paths to selection without clearing existing. Returns count of newly added."""
        before = len(self._selected_paths)
        self._selected_paths.update(paths)
        added = len(self._selected_paths) - before
        if added > 0:
            self._clear_folder_state_cache()
            self._emit_tree_checkstate_changed()
            self.selection_changed.emit(set(self._selected_paths))
        return added
    
    def remove_paths_from_selection(self, paths: Set[str]) -> int:
        """Remove specific paths from selection. Returns count removed."""
        before = len(self._selected_paths)
        self._selected_paths -= paths
        removed = before - len(self._selected_paths)
        if removed > 0:
            self._clear_folder_state_cache()
            self._emit_tree_checkstate_changed()
            self.selection_changed.emit(set(self._selected_paths))
        return removed
    
    def select_all(self) -> None:
        """Select tất cả files."""
        self._select_all_recursive(self._get_root_parent())
        self._clear_folder_state_cache()
        self._emit_tree_checkstate_changed()
        self.selection_changed.emit(set(self._selected_paths))
    
    def deselect_all(self) -> None:
        """Deselect tất cả."""
        self._selected_paths.clear()
        self._last_resolved_files.clear()
        self._token_cache.clear()
        self._clear_folder_state_cache()
        self._emit_tree_checkstate_changed()
        self.selection_changed.emit(set(self._selected_paths))
    
    def update_token_count(self, path: str, count: int) -> None:
        """
        Cập nhật token count cho 1 file (gọi từ background thread qua signal).
        
        Chỉ emit dataChanged cho row tương ứng - KHÔNG re-render toàn tree.
        """
        self._token_cache[path] = count
        
        node = self._path_to_node.get(path)
        if node is not None:
            idx = self._node_to_index(node)
            if idx.isValid():
                self.dataChanged.emit(idx, idx, [FileTreeRoles.TOKEN_COUNT_ROLE])
        
        self.token_count_updated.emit(path, count)

    def update_token_counts_batch(self, counts: Dict[str, int]) -> None:
        """Batch update token counts và emit dataChanged cho files + ancestor folders."""
        if not counts:
            return

        self._token_cache.update(counts)

        # Emit dataChanged for updated files + their ancestor folders
        changed_nodes: Set[TreeNode] = set()
        for path in counts:
            node = self._path_to_node.get(path)
            if node is not None:
                changed_nodes.add(node)
                # Also mark ancestor folders for repaint (token total changed)
                parent = node.parent
                while parent is not None and parent is not self._invisible_root:
                    changed_nodes.add(parent)
                    parent = parent.parent

        for node in changed_nodes:
            idx = self._node_to_index(node)
            if idx.isValid():
                self.dataChanged.emit(idx, idx, [FileTreeRoles.TOKEN_COUNT_ROLE])

        for path, count in counts.items():
            self.token_count_updated.emit(path, count)
    
    def update_line_count(self, path: str, count: int) -> None:
        """Cập nhật line count cho 1 file."""
        self._line_cache[path] = count
        
        node = self._path_to_node.get(path)
        if node is not None:
            idx = self._node_to_index(node)
            if idx.isValid():
                self.dataChanged.emit(idx, idx, [FileTreeRoles.LINE_COUNT_ROLE])
    
    def get_total_tokens(self) -> int:
        """Tính tổng tokens cho tất cả selected files (bao gồm deep files).
        
        Dùng _last_resolved_files nếu có (set bởi token counting worker),
        fallback sang _selected_paths.
        """
        total = 0
        paths_to_check = self._last_resolved_files if self._last_resolved_files else self._selected_paths
        for path in paths_to_check:
            if path in self._token_cache:
                total += self._token_cache[path]
        return total
    
    def get_selected_file_count(self) -> int:
        """Get số files đã selected (bao gồm deep unloaded files).
        
        Dùng _last_resolved_files nếu đã có (set bởi background token counting).
        Nếu chưa có, trả về quick estimate từ _selected_paths để KHÔNG block UI.
        Accurate count sẽ update sau khi token counting hoàn thành.
        """
        if self._last_resolved_files:
            return len(self._last_resolved_files)
        # Quick estimate: count non-folder paths, treat unloaded folders as 1 each
        # Tránh gọi get_selected_paths() synchronously vì nó scan disk
        count = 0
        for p in self._selected_paths:
            node = self._path_to_node.get(p)
            if node is None or not node.is_dir:
                count += 1
            else:
                # Folder — estimate có files bên trong
                count += max(1, node.child_count())
        return count
    
    @property
    def generation(self) -> int:
        """Current generation counter. Workers compare this to detect staleness."""
        with self._generation_lock:
            return self._generation
    
    def _build_search_index_async(self, workspace_path: Path) -> None:
        """Build flat search index trong background thread via os.walk.
        
        Dùng cùng logic ignore với load_folder_children: pathspec (EXTENDED_IGNORE,
        excluded patterns, gitignore), is_binary_file, is_system_path.
        Đảm bảo search results khớp với items hiển thị trong tree.
        """
        generation = self.generation  # Snapshot
        
        def _build():
            from core.constants import DIRECTORY_QUICK_SKIP, EXTENDED_IGNORE_PATTERNS
            from core.utils.file_utils import (
                is_binary_file, is_system_path,
                get_cached_pathspec, _read_gitignore,
            )
            from views.settings_view_qt import get_excluded_patterns, get_use_gitignore
            
            # Build pathspec giống _collect_files_from_disk
            ignore_patterns: List[str] = [".git", ".hg", ".svn"]
            ignore_patterns.extend(EXTENDED_IGNORE_PATTERNS)
            excluded = get_excluded_patterns()
            if excluded:
                ignore_patterns.extend(excluded)
            
            # Tìm git root từ workspace
            root_path = workspace_path
            while root_path.parent != root_path:
                if (root_path / ".git").exists():
                    break
                root_path = root_path.parent
            
            if get_use_gitignore():
                gitignore_patterns = _read_gitignore(root_path)
                ignore_patterns.extend(gitignore_patterns)
            
            spec = get_cached_pathspec(root_path, list(ignore_patterns))
            root_path_str = str(root_path)
            
            index: Dict[str, List[str]] = {}
            try:
                for dirpath, dirnames, filenames in os.walk(str(workspace_path)):
                    if self.generation != generation:
                        return
                    
                    dirnames[:] = sorted(d for d in dirnames if d not in DIRECTORY_QUICK_SKIP)
                    
                    for filename in filenames:
                        full_path = os.path.join(dirpath, filename)
                        entry = Path(full_path)
                        
                        if is_system_path(entry) or is_binary_file(entry):
                            continue
                        
                        try:
                            rel_path_str = os.path.relpath(full_path, root_path_str)
                        except ValueError:
                            rel_path_str = filename
                        
                        if spec.match_file(rel_path_str):
                            continue
                        
                        key = filename.lower()
                        if key not in index:
                            index[key] = []
                        index[key].append(full_path)
            except Exception:
                pass
            
            # Check và ghi phải atomic để tránh race: load_tree có thể đã chạy giữa
            # check và write, khiến thread cũ ghi đè index mới bằng data stale.
            with self._generation_lock:
                if self._generation == generation:
                    self._search_index = index
                    self._search_index_ready = True
        
        thread = threading.Thread(target=_build, daemon=True)
        thread.start()
    
    def search_files(self, query: str) -> List[str]:
        """
        Search files by query using flat index.
        
        Returns list of full paths matching query (case-insensitive substring).
        Independent of lazy loading — works even if folders are not expanded.
        """
        if not self._search_index_ready:
            return []
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return []
        results: List[str] = []
        
        for filename_lower, paths in self._search_index.items():
            if query_lower in filename_lower:
                results.extend(paths)
        
        results.sort()
        return results
    
    def clear_token_cache(self) -> None:
        """Clear token cache."""
        self._token_cache.clear()
    
    # ===== Private Helpers =====
    
    def _get_root_parent(self) -> TreeNode:
        """Get invisible root node."""
        return self._invisible_root

    def _clear_folder_state_cache(self) -> None:
        self._folder_state_cache.clear()

    def _emit_tree_checkstate_changed(self) -> None:
        if not self._root_node:
            return

        if self.rowCount() == 0:
            return

        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, 0)
        if top_left.isValid() and bottom_right.isValid():
            self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])
    
    def _build_path_index(self, node: TreeNode) -> None:
        """Build path -> node index (recursive)."""
        self._path_to_node[node.path] = node
        for child in node.children:
            self._build_path_index(child)
    
    def _node_to_index(self, node: TreeNode) -> QModelIndex:
        """Convert TreeNode sang QModelIndex."""
        if node is self._invisible_root or node.parent is None:
            return QModelIndex()
        return self.createIndex(node.row, 0, node)
    
    def _select_node(self, node: TreeNode) -> None:
        """Select node và tất cả children (recursive)."""
        self._selected_paths.add(node.path)
        if node.is_dir:
            for child in node.children:
                self._select_node(child)
    
    def _deselect_node(self, node: TreeNode) -> None:
        """Deselect node và tất cả children (recursive)."""
        self._selected_paths.discard(node.path)
        if node.is_dir:
            for child in node.children:
                self._deselect_node(child)
    
    def _select_all_recursive(self, node: TreeNode) -> None:
        """Recursively select tất cả nodes."""
        self._selected_paths.add(node.path)
        for child in node.children:
            self._select_all_recursive(child)
    
    def _get_folder_check_state(self, node: TreeNode) -> Qt.CheckState:
        """
        Tính tri-state check state cho folder.
        
        - Checked: tất cả loaded children đều selected
        - PartiallyChecked: một số children selected
        - Unchecked: không có children selected
        """
        cached = self._folder_state_cache.get(node.path)
        if cached is not None:
            return cached

        if not node.children:
            state = Qt.CheckState.Checked if node.path in self._selected_paths else Qt.CheckState.Unchecked
            self._folder_state_cache[node.path] = state
            return state
        
        all_selected = True
        any_selected = False
        
        for child in node.children:
            if child.path in self._selected_paths:
                any_selected = True
            else:
                all_selected = False
            
            # Recurse vào subfolders
            if child.is_dir and child.children:
                child_state = self._get_folder_check_state(child)
                if child_state == Qt.CheckState.Checked:
                    any_selected = True
                elif child_state == Qt.CheckState.PartiallyChecked:
                    any_selected = True
                    all_selected = False
                else:
                    all_selected = False

            if any_selected and not all_selected:
                self._folder_state_cache[node.path] = Qt.CheckState.PartiallyChecked
                return Qt.CheckState.PartiallyChecked
        
        if all_selected and any_selected:
            state = Qt.CheckState.Checked
        elif any_selected:
            state = Qt.CheckState.PartiallyChecked
        else:
            state = Qt.CheckState.Unchecked

        self._folder_state_cache[node.path] = state
        return state
    
    def _get_folder_token_total(self, node: TreeNode) -> Optional[int]:
        """
        Tính tổng tokens của tất cả selected files trong folder.
        
        Chỉ tính files đã có token count trong cache.
        Returns None nếu không có file nào selected hoặc chưa counted.
        """
        total = 0
        has_any = False
        folder_prefix = node.path + "/"
        
        for file_path, count in self._token_cache.items():
            if file_path.startswith(folder_prefix) and count > 0:
                # Chỉ tính files đang selected
                if file_path in self._selected_paths or file_path in self._last_resolved_files:
                    total += count
                    has_any = True
        
        return total if has_any else None
    
    def _emit_parent_changes(self, node: TreeNode) -> None:
        """Emit dataChanged cho tất cả ancestors (cập nhật tri-state)."""
        current = node.parent
        while current is not None and current is not self._invisible_root:
            idx = self._node_to_index(current)
            if idx.isValid():
                self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.CheckStateRole])
            current = current.parent


class TokenCountWorker(QRunnable):
    """
    Background worker để đếm tokens cho các file đã selected.
    
    Emit kết quả từng file qua signals - model receive và update từng row.
    Uses generation counter to detect workspace changes and abort early.
    """
    
    class Signals(QObject):
        token_counted = Signal(str, int)  # (file_path, token_count)
        token_counts_batch = Signal(dict)  # Dict[str, int]
        finished = Signal()
        error = Signal(str)
    
    def __init__(self, file_paths: List[str], generation: int = 0):
        super().__init__()
        self.file_paths = file_paths
        self.signals = self.Signals()
        self.setAutoDelete(True)
        self._cancelled = False
        self._batch_size = 25
        self._generation = generation  # Snapshot at creation time
    
    def cancel(self) -> None:
        """Cancel worker."""
        self._cancelled = True
    
    @property
    def generation(self) -> int:
        """Generation this worker was created for."""
        return self._generation
    
    @Slot()
    def run(self) -> None:
        """Đếm tokens cho tất cả files. Skip binary/image files."""
        from core.token_counter import count_tokens
        from core.utils.file_utils import is_binary_file
        
        # Max file size for token counting (5MB) - prevents OOM on large binaries
        MAX_TOKEN_FILE_SIZE = 5 * 1024 * 1024
        
        try:
            batch: Dict[str, int] = {}
            for file_path in self.file_paths:
                if self._cancelled:
                    break
                
                try:
                    path = Path(file_path)
                    if not path.exists() or not path.is_file():
                        continue
                    
                    # Skip binary/image files (check magic bytes, not just extension)
                    if is_binary_file(path):
                        batch[file_path] = 0
                        continue
                    
                    # Skip files too large for token counting
                    try:
                        if path.stat().st_size > MAX_TOKEN_FILE_SIZE:
                            batch[file_path] = 0
                            continue
                    except OSError:
                        continue
                    
                    content = path.read_text(encoding="utf-8", errors="replace")
                    tokens = count_tokens(content)
                    batch[file_path] = tokens

                    if len(batch) >= self._batch_size:
                        self.signals.token_counts_batch.emit(dict(batch))
                        batch.clear()
                except Exception as e:
                    logger.debug(f"Error counting tokens for {file_path}: {e}")

            if not self._cancelled and batch:
                self.signals.token_counts_batch.emit(dict(batch))
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()
