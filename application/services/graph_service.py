from __future__ import annotations

import threading
import pickle
import os
import time
from pathlib import Path
from typing import Optional, Any
from collections import OrderedDict
from PySide6.QtCore import QObject, Signal

from domain.relationships.builder import GraphBuilder
from domain.relationships.graph import RelationshipGraph
from domain.relationships.port import IRelationshipGraphProvider
from infrastructure.filesystem.ignore_engine import IgnoreEngine


class GraphSignals(QObject):
    """Signals để UI lắng nghe quá trình build graph. (Thread-safe)"""

    build_started = Signal()
    build_status = Signal(str)  # Thông báo trạng thái (e.g. "Loading cache...")
    build_progress = Signal(int, int)  # (current, total)
    build_finished = Signal(float, int)  # (duration_seconds, token_count)
    build_error = Signal(str)


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

        # AST Tree + Adjacency Cache: source_abs -> (mtime, tree, hash, targets) (Phase 5)
        # Sử dụng OrderedDict để implement LRU eviction
        self._tree_cache: OrderedDict[str, tuple[float, Any, str, set[str]]] = (
            OrderedDict()
        )
        self._MAX_TREE_CACHE = 500

        # Signals cho UI UX Pro Max
        self.signals = GraphSignals()

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
        self.signals.build_started.emit()

        try:
            # Tải cache từ disk nếu bộ nhớ rỗng (Lần đầu khởi động app)
            if not self._tree_cache:
                self.signals.build_status.emit("Loading semantic cache from disk...")
                self.load_cache(workspace_root)

            # Build bên ngoài lock để không block readers
            self.signals.build_status.emit("Analyzing project structure...")
            graph = self._build_graph_sync(workspace_root)

            # Lưu cache sau khi hoàn tất build
            self.save_cache(workspace_root)

            duration = time.time() - start
            # TODO: Truyền token_count thực tế nếu có
            self.signals.build_finished.emit(duration, 0)
        except Exception as e:
            # Bug #3 Fix: Reset flag nếu build thất bại
            with self._lock:
                self._building = False
            self.signals.build_error.emit(str(e))
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

        # Chúng ta có thể bổ sung callback vào Builder nếu muốn xem tiến trình chi tiết
        # Hiện tại ta coi build() là một khối duy nhất cho 10k files (Nhưng tốn 1-3s)
        self.signals.build_status.emit("Connecting relationships (Adjacency)...")
        graph = builder.build(
            file_paths=file_paths,
            existing_resolver=None,
            max_codemap_files=500,
            imports_max_depth=2,
            tree_cache=self._tree_cache,  # Pass cache to builder
        )

        # LRU Eviction: Giới hạn bộ nhớ cho AST trees
        while len(self._tree_cache) > self._MAX_TREE_CACHE:
            self._tree_cache.popitem(last=False)

        return graph

    def save_cache(self, workspace_root: Path) -> None:
        """Lưu Adjacency Cache xuống ổ đĩa (.synapse/graph_cache.pkl)."""
        from shared.logging_config import log_info, log_error

        cache_dir = workspace_root / ".synapse"
        cache_file = cache_dir / "graph_cache.pkl"

        try:
            cache_dir.mkdir(parents=True, exist_ok=True)

            # CHUẨN BỊ DATA: KHÔNG lưu Tree object vì là C-native, chỉ lưu mtime, hash, targets
            # record: (mtime, tree, hash, targets) -> (mtime, None, hash, targets)
            savable_cache = OrderedDict()
            with self._lock:
                for path, data in self._tree_cache.items():
                    # data: (mtime, tree, hash, targets)
                    savable_cache[path] = (data[0], None, data[2], data[3])

            with open(cache_file, "wb") as f:
                pickle.dump(savable_cache, f)

            log_info(
                f"[GraphService] Performance cache saved: {len(savable_cache)} files"
            )
        except Exception as e:
            log_error(f"[GraphService] Failed to save cache: {e}")

    def load_cache(self, workspace_root: Path) -> None:
        """Tải Adjacency Cache từ ổ đĩa."""
        from shared.logging_config import log_info

        cache_file = workspace_root / ".synapse" / "graph_cache.pkl"
        if not cache_file.exists():
            return

        try:
            with open(cache_file, "rb") as f:
                loaded_cache = pickle.load(f)

            if isinstance(loaded_cache, (dict, OrderedDict)):
                with self._lock:
                    # Update local cache, giữ nguyên tree nếu đã có (Dù load_cache thường gọi lúc khởi động)
                    for path, data in loaded_cache.items():
                        if path not in self._tree_cache:
                            self._tree_cache[path] = data
                log_info(
                    f"[GraphService] Performance cache loaded: {len(loaded_cache)} files"
                )
        except Exception:
            # Xóa cache file nếu bị lỗi (checksum mismatch, etc.)
            try:
                os.remove(cache_file)
            except Exception:
                pass
