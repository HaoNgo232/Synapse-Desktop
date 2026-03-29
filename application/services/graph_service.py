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

        Nếu graph đang build cho cùng workspace, đợi cho đến khi xong.
        Phù hợp cho các luồng synchronous như MCP server, scripts nội bộ.
        """
        from shared.logging_config import log_info
        import time

        workspace_root = workspace_root.resolve()

        # Polling loop: đợi nếu background build đang chạy cho cùng workspace
        # Hạn chế waiting time để tránh treo process quá lâu (ví dụ 60s)
        MAX_WAIT_SECONDS = 60
        POLL_INTERVAL = 0.2
        waited = 0.0

        while True:
            with self._lock:
                # Cache hit: graph đã sẵn sàng cho workspace này
                if self._graph is not None and self._workspace_root == workspace_root:
                    log_info(
                        f"[GraphService] ensure_built: cache hit "
                        f"({len(self._graph.all_files())} files)"
                    )
                    return self._graph

                # Nếu không có ai đang build -> tự mình build
                if not self._building:
                    break

                # Có build đang chạy nhưng cho workspace khác -> không đợi, trigger build mới
                if self._workspace_root != workspace_root:
                    break

            # Nếu background build đang chạy cho CÙNG workspace -> đợi
            if waited >= MAX_WAIT_SECONDS:
                log_info(
                    f"[GraphService] ensure_built: waited {MAX_WAIT_SECONDS}s, "
                    f"falling back to sync build"
                )
                break

            time.sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL

        # Nếu đến đây có nghĩa là cần tự build (không có background build hoặc timeout)
        with self._lock:
            # Double check sau khi thoát loop để tránh race condition cuối cùng
            if self._graph is not None and self._workspace_root == workspace_root:
                return self._graph

            # Đánh dấu đang build (blocking path)
            self._building = True
            current_generation = self._generation + 1
            self._generation = current_generation

        log_info(f"[GraphService] ensure_built: building graph for {workspace_root}...")
        start = time.time()

        try:
            # Build bên ngoài lock để không block readers
            graph = self._build_graph_sync(workspace_root)
        except Exception as e:
            # Bug #3 Fix: Reset flag nếu build thất bại
            with self._lock:
                self._building = False
            raise e

        duration = time.time() - start
        log_info(
            f"[GraphService] ensure_built: completed in {duration:.2f}s "
            f"({len(graph.all_files())} files, {graph.edge_count()} edges)"
        )

        with self._lock:
            # Chỉ swap nếu generation không bị ghi đè (atomic swap)
            if current_generation == self._generation:
                self._graph = graph
                self._workspace_root = workspace_root

            # Luôn reset flag khi xong (dù swap hay discard)
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
        [Feature Disabled] - Tính năng update graph khi file đổi đã bị tắt theo yêu cầu.
        """
        pass

    def _clone_graph(self, graph: RelationshipGraph) -> RelationshipGraph:
        """Clone graph bằng cách copy tất cả edges."""
        new_graph = RelationshipGraph()
        for file_path in graph.all_files():
            edges = graph.get_edges_from(file_path)
            new_graph.add_edges(edges)
        return new_graph

    def on_files_deleted(self, deleted_files: list[str]) -> None:
        """
        [Feature Disabled] - Tính năng update graph khi file bị xóa đã bị tắt.
        """
        pass

    def on_workspace_changed(self, workspace_root: Path) -> None:
        """
        Gọi khi user đổi workspace: chuẩn bị workspace mới và áp dụng lazy-load.

        Graph sẽ không bị trigger build ngầm (tránh treo/nặng lúc khởi động).
        Thay vào đó, nó sẽ được build đồng bộ (hoặc ngầm) khi các modules thực sự cần (ví dụ: qua ensure_built).
        """
        from shared.logging_config import log_info

        workspace_root = workspace_root.resolve()
        log_info(f"[GraphService] on_workspace_changed -> {workspace_root} (Lazy)")

        with self._lock:
            self._workspace_root = workspace_root
            self._generation += 1
            self._graph = None
            self._building = False

    # ===== Internal helpers =====

    def _build_graph_background(self, workspace_root: Path, generation: int) -> None:
        """
        Build graph trên background thread, sau đó swap nếu generation còn hợp lệ.
        """
        from shared.logging_config import log_info, log_error
        import time

        log_info(f"[GraphService] Background build started for {workspace_root}")
        start = time.time()

        try:
            graph = self._build_graph_sync(workspace_root)
        except Exception as e:
            log_error("[GraphService] Background build FAILED", exc=e)
            with self._lock:
                # Reset flag nếu background build lỗi
                self._building = False
            return

        with self._lock:
            # Reset flag trong mọi trường hợp (kể cả discard)
            self._building = False

            if generation != self._generation:
                log_info("[GraphService] Build discarded (new generation)")
                return

            self._graph = graph
            self._workspace_root = workspace_root
            duration = time.time() - start
            log_info(
                f"[GraphService] Build completed in {duration:.2f}s "
                f"({len(graph.all_files())} files, {graph.edge_count()} edges)"
            )

    def _build_graph_sync(self, workspace_root: Path) -> RelationshipGraph:
        """
        Build RelationshipGraph một cách synchronous cho workspace.
        """

        # Thu thập tất cả file trong workspace sử dụng workspace_index
        from application.services.workspace_index import collect_files_from_disk

        all_files = collect_files_from_disk(
            workspace_root,
            workspace_path=workspace_root,
            ignore_engine=self._ignore_engine,  # Truyền ignore_engine để respect excluded patterns
        )

        file_paths = [p for p in all_files if Path(p).is_file()]

        builder = GraphBuilder(workspace_root=workspace_root)
        graph = builder.build(
            file_paths=file_paths,
            existing_resolver=None,
            max_codemap_files=500,
            imports_max_depth=2,
        )
        return graph
