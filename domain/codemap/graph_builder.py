"""
Graph Builder - Build và manage CodeMap cho workspace

Module này build CodeMap cho files/workspace và provide query API.
"""

from pathlib import Path
from typing import Optional, Set
from core.utils.file_utils import TreeItem

from core.codemaps.types import CodeMap
from core.codemaps.symbol_extractor import extract_symbols
from core.codemaps.relationship_extractor import extract_relationships


class CodeMapBuilder:
    """
    Build và manage CodeMap cho workspace.

    Features:
    - Build CodeMap cho single file
    - Build CodeMap cho entire workspace
    - Query API (get_related_symbols, get_callers, get_callees)
    - Cache layer (future enhancement)

    Attributes:
        workspace_root: Root path của workspace
        codemaps: Cache của CodeMaps indexed by file path
    """

    def __init__(self, workspace_root: Path):
        """
        Khởi tạo CodeMapBuilder.

        Args:
            workspace_root: Root path của workspace
        """
        self.workspace_root = workspace_root
        self.codemaps: dict[str, CodeMap] = {}

    def build_for_file(
        self, file_path: str, content: Optional[str] = None
    ) -> Optional[CodeMap]:
        """
        Build CodeMap cho một file.

        Args:
            file_path: Đường dẫn file (absolute hoặc relative to workspace)
            content: Nội dung file (optional, sẽ đọc từ disk nếu None)

        Returns:
            CodeMap object hoặc None nếu failed
        """
        # Read content nếu chưa có
        if content is None:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                return None

        # Extract symbols
        symbols = extract_symbols(file_path, content)

        # Extract relationships
        # Collect known symbols từ current file
        known_symbols = {s.name for s in symbols}
        relationships = extract_relationships(file_path, content, known_symbols)

        # Create CodeMap
        codemap = CodeMap(
            file_path=file_path,
            symbols=symbols,
            relationships=relationships,
        )

        # Cache it
        self.codemaps[file_path] = codemap

        return codemap

    def build_for_workspace(self, tree: TreeItem) -> dict[str, CodeMap]:
        """
        Build CodeMap cho toàn bộ workspace.

        Args:
            tree: TreeItem root của file tree

        Returns:
            Dict mapping file_path -> CodeMap
        """
        # Collect all files
        files: list[str] = []
        self._collect_files(tree, files)

        # Build CodeMap cho từng file
        for file_path in files:
            self.build_for_file(file_path)

        return self.codemaps

    def _collect_files(self, item: TreeItem, result: list[str]) -> None:
        """Recursively collect all file paths từ tree."""
        if not item.is_dir:
            result.append(item.path)
        else:
            for child in item.children:
                self._collect_files(child, result)

    def get_codemap(self, file_path: str) -> Optional[CodeMap]:
        """
        Lấy CodeMap cho file.

        Args:
            file_path: File path

        Returns:
            CodeMap hoặc None nếu chưa build
        """
        return self.codemaps.get(file_path)

    def get_related_symbols(
        self, symbol_name: str, depth: int = 1, file_path: Optional[str] = None
    ) -> Set[str]:
        """
        Lấy tất cả symbols liên quan đến symbol_name.

        Args:
            symbol_name: Tên symbol cần tìm
            depth: Độ sâu đệ quy (1 = direct relationships only)
            file_path: File path để scope search (optional)

        Returns:
            Set of related symbol names
        """
        related: Set[str] = set()
        visited: Set[str] = set()

        def traverse(name: str, current_depth: int):
            if current_depth > depth or name in visited:
                return

            visited.add(name)

            # Search trong tất cả codemaps (hoặc chỉ file_path nếu có)
            codemaps_to_search = (
                [self.codemaps[file_path]]
                if file_path and file_path in self.codemaps
                else self.codemaps.values()
            )

            for codemap in codemaps_to_search:
                # Find relationships where source = name
                for rel in codemap.get_relationships_by_source(name):
                    related.add(rel.target)
                    if current_depth < depth:
                        traverse(rel.target, current_depth + 1)

                # Find relationships where target = name (reverse)
                for rel in codemap.get_relationships_by_target(name):
                    related.add(rel.source)
                    if current_depth < depth:
                        traverse(rel.source, current_depth + 1)

        traverse(symbol_name, 0)
        return related

    def get_callers(self, function_name: str) -> list[str]:
        """
        Lấy tất cả functions/methods gọi function_name.

        Args:
            function_name: Tên function cần tìm

        Returns:
            List of caller names
        """
        callers: list[str] = []

        for codemap in self.codemaps.values():
            for rel in codemap.relationships:
                if rel.target == function_name and rel.kind.value == "calls":
                    callers.append(rel.source)

        return callers

    def get_callees(self, function_name: str) -> list[str]:
        """
        Lấy tất cả functions/methods được gọi bởi function_name.

        Args:
            function_name: Tên function cần tìm

        Returns:
            List of callee names
        """
        callees: list[str] = []

        for codemap in self.codemaps.values():
            for rel in codemap.relationships:
                if rel.source == function_name and rel.kind.value == "calls":
                    callees.append(rel.target)

        return callees

    def clear_cache(self) -> None:
        """Clear tất cả cached CodeMaps."""
        self.codemaps.clear()

    def invalidate_file(self, file_path: str) -> None:
        """
        Invalidate cache cho một file.

        Args:
            file_path: File path cần invalidate
        """
        if file_path in self.codemaps:
            del self.codemaps[file_path]
