from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from domain.relationships.builder import GraphBuilder
from domain.relationships.graph import RelationshipGraph
from domain.relationships.port import IRelationshipGraphProvider
from infrastructure.filesystem.ignore_engine import IgnoreEngine

"""
GraphService - Quan ly lifecycle cua RelationshipGraph o application layer.

Chịu trách nhiệm:
- Build RelationshipGraph cho workspace (background hoặc blocking)
- Cache instance graph hiện tại
- Invalidate khi workspace thay đổi

Lớp này implement IRelationshipGraphProvider để các layer khác
(presentation, MCP server, v.v.) chỉ phụ thuộc vào Protocol.
"""


class GraphService(IRelationshipGraphProvider):
    """
    Service application-level để build và cung cấp RelationshipGraph.

    Thiết kế:
    - Thread-safe swap: build graph mới trên background thread,
      sau đó swap reference vào `_graph` bên trong lock.
    - READ-heavy, WRITE-rare: hầu hết callers chỉ đọc graph.
    """

    def __init__(self, ignore_engine: Optional[IgnoreEngine] = None) -> None:
        """
        Khởi tạo GraphService.

        Args:
            ignore_engine: Engine dùng để filter files theo ignore patterns.
        """

        self._graph: Optional[RelationshipGraph] = None
        self._workspace_root: Optional[Path] = None
        self._lock = threading.Lock()
        self._generation: int = 0
        self._building: bool = False
        self._ignore_engine = ignore_engine

    # ===== IRelationshipGraphProvider API =====

    def get_graph(self) -> RelationshipGraph | None:
        """
        Trả về graph hiện tại (có thể None nếu chưa build xong).

        Caller nên fallback sang DependencyResolver khi nhận None
        để đảm bảo trải nghiệm người dùng không bị chặn.
        """

        with self._lock:
            return self._graph

    def ensure_built(self, workspace_root: Path) -> RelationshipGraph:
        """
        Đảm bảo graph đã được build cho workspace.

        Phù hợp cho các luồng synchronous như MCP server, scripts nội bộ.
        Nếu graph đang build cho cùng workspace, chờ đến khi xong.
        """

        workspace_root = workspace_root.resolve()

        with self._lock:
            # Nếu đã có graph cho workspace này thì trả về luôn
            if self._graph is not None and self._workspace_root == workspace_root:
                return self._graph

            # Đánh dấu đang build (blocking path)
            self._building = True
            current_generation = self._generation + 1
            self._generation = current_generation

        # Build bên ngoài lock để tránh block readers
        graph = self._build_graph_sync(workspace_root)

        with self._lock:
            # Chỉ swap nếu generation không bị ghi đè
            if current_generation == self._generation:
                self._graph = graph
                self._workspace_root = workspace_root
                self._building = False
                return graph
            else:
                # Generation conflict: có build khác đã override
                # Trả về graph vừa build thay vì self._graph (có thể là workspace khác)
                self._building = False
                return graph

    def invalidate(self) -> None:
        """
        Đánh dấu graph hiện tại là stale.

        Lần build tiếp theo (ensure_built/on_workspace_changed) sẽ tạo lại.
        """

        with self._lock:
            self._graph = None
            self._generation += 1

    # ===== Public API bổ sung cho UI/File watcher =====

    def on_files_changed(self, changed_files: list[str]) -> None:
        """
        Incremental update khi một hoặc nhiều files thay đổi.

        Chiến lược đơn giản:
        - Nếu chưa có graph thì bỏ qua (sẽ full-build sau).
        - Xóa mọi edges liên quan tới các files này.
        - Rebuild edges mới cho từng file và merge vào graph hiện tại.
        """

        if not changed_files:
            return

        with self._lock:
            if self._graph is None or self._workspace_root is None:
                return
            workspace_root = self._workspace_root
            current_generation = self._generation  # Capture generation

        builder = GraphBuilder(workspace_root=workspace_root)

        # Chuẩn hóa đường dẫn theo workspace
        normalized: list[str] = []
        for path_str in changed_files:
            p = Path(path_str)
            if not p.is_absolute():
                p = workspace_root / p
            if p.exists() and p.is_file():
                try:
                    normalized.append(str(p.resolve()))
                except OSError:
                    normalized.append(str(p))

        if not normalized:
            return

        incremental_graph = builder.build(
            file_paths=normalized,
            existing_resolver=None,
            max_codemap_files=len(normalized),
            imports_max_depth=2,
        )

        with self._lock:
            # Check generation để tránh merge stale data
            if current_generation != self._generation:
                return  # Workspace đã thay đổi, discard result

            if self._graph is None:
                self._graph = incremental_graph
                return

            # Copy-on-write: Clone graph trước khi mutate để tránh race với readers
            new_graph = self._clone_graph(self._graph)

            for file_path in normalized:
                new_graph.remove_edges_for_file(file_path)

            for file_path in normalized:
                edges = incremental_graph.get_edges_from(file_path)
                if edges:
                    new_graph.add_edges(edges)

            # Atomic swap
            self._graph = new_graph

    def _clone_graph(self, graph: RelationshipGraph) -> RelationshipGraph:
        """Clone graph bằng cách copy tất cả edges."""
        new_graph = RelationshipGraph()
        for file_path in graph.all_files():
            edges = graph.get_edges_from(file_path)
            new_graph.add_edges(edges)
        return new_graph

    def on_files_deleted(self, deleted_files: list[str]) -> None:
        """
        Xử lý khi files bị xóa - remove stale edges khỏi graph.

        Args:
            deleted_files: Danh sách đường dẫn files đã bị xóa
        """
        if not deleted_files:
            return

        with self._lock:
            if self._graph is None or self._workspace_root is None:
                return

            workspace_root = self._workspace_root

            for path_str in deleted_files:
                p = Path(path_str)
                if not p.is_absolute():
                    p = workspace_root / p
                try:
                    abs_path = str(p.resolve())
                except OSError:
                    abs_path = str(p)

                self._graph.remove_edges_for_file(abs_path)

    def on_workspace_changed(self, workspace_root: Path) -> None:
        """
        Gọi khi user đổi workspace: trigger full build trên background thread.

        Method này không block UI; callers có thể tiếp tục dùng fallback
        DependencyResolver cho đến khi graph sẵn sàng.
        """

        workspace_root = workspace_root.resolve()

        with self._lock:
            self._workspace_root = workspace_root
            self._generation += 1
            generation = self._generation

        thread = threading.Thread(
            target=self._build_graph_background,
            args=(workspace_root, generation),
            daemon=True,
        )
        thread.start()

    # ===== Internal helpers =====

    def _build_graph_background(self, workspace_root: Path, generation: int) -> None:
        """
        Build graph trên background thread, sau đó swap nếu generation còn hợp lệ.
        """

        graph = self._build_graph_sync(workspace_root)

        with self._lock:
            if generation != self._generation:
                # Có build mới hơn đã được trigger, bỏ qua kết quả cũ
                return
            self._graph = graph
            self._workspace_root = workspace_root

    def _build_graph_sync(self, workspace_root: Path) -> RelationshipGraph:
        """
        Build RelationshipGraph một cách synchronous cho workspace.
        """

        # Thu thập tất cả file trong workspace sử dụng workspace_index
        from application.services.workspace_index import collect_files_from_disk

        all_files = collect_files_from_disk(
            workspace_root,
            workspace_path=workspace_root,
        )

        # Áp dụng ignore_engine nếu có
        file_paths: list[str] = []
        pathspec = None
        if self._ignore_engine is not None:
            pathspec = self._ignore_engine.build_pathspec(workspace_root)

        for path_str in all_files:
            p = Path(path_str)
            if not p.is_file():
                continue
            if pathspec is not None:
                rel_path = p.relative_to(workspace_root)
                if pathspec.match_file(str(rel_path)):
                    continue
            file_paths.append(str(p))

        builder = GraphBuilder(workspace_root=workspace_root)
        graph = builder.build(
            file_paths=file_paths,
            existing_resolver=None,
            max_codemap_files=500,
            imports_max_depth=2,
        )
        return graph
