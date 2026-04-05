from __future__ import annotations
from typing import List, Optional, Any, Dict
from pathlib import Path
from domain.relationships.graph import RelationshipGraph
from domain.relationships.builder import GraphBuilder


class RelationshipService:
    """
    Domain Service quản lý RelationshipGraph.
    Chứa business logic thuần túy về việc xây dựng và truy vấn quan hệ giữa các files.
    """

    def __init__(self):
        self._graph: Optional[RelationshipGraph] = None
        self._workspace_root: Optional[Path] = None

    def build_for_workspace(
        self,
        workspace_root: Path,
        file_paths: List[str],
        tree_cache: Optional[Dict[str, Any]] = None,
    ) -> RelationshipGraph:
        """
        Xây dựng graph cho workspace từ danh sách file paths.
        """
        self._workspace_root = workspace_root.resolve()

        # Khởi tạo builder cho workspace cụ thể này
        builder = GraphBuilder(workspace_root=self._workspace_root)

        # Gọi Domain Builder để thực hiện logic phân tích AST (Tree-sitter)
        self._graph = builder.build(file_paths=file_paths, tree_cache=tree_cache)
        return self._graph

    def set_graph(self, graph: RelationshipGraph, workspace_root: Path) -> None:
        """Thực hiện atomic swap graph mới."""
        self._graph = graph
        self._workspace_root = workspace_root.resolve()

    def get_current_graph(self) -> Optional[RelationshipGraph]:
        return self._graph

    def reset(self) -> None:
        self._graph = None
        self._workspace_root = None
