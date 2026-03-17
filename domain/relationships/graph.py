from __future__ import annotations

from collections import deque
from typing import Optional, Set

from domain.relationships.types import Edge, EdgeKind, FileNode

"""
RelationshipGraph - Cấu trúc dữ liệu core cho quan hệ giữa các file.

Graph này là single source of truth cho mọi quan hệ file-level
trong workspace (imports, calls, inherits, tests...).

Thiết kế:
- Pure data structure: không đọc/ghi disk, không parse code
- Được build bởi builder ở layer khác, sau đó chỉ đọc (read-only)
- Hỗ trợ truy vấn BFS theo độ sâu và lọc theo EdgeKind
"""


class RelationshipGraph:
    """
    Graph biểu diễn quan hệ giữa các file trong workspace.

    Thiết kế hướng tới:
    - Truy vấn nhanh (read-heavy)
    - Build rõ ràng (write-rare)
    - Dễ dàng rebuild bằng cách tạo instance mới rồi swap reference
    """

    def __init__(self) -> None:
        # adjacency_out: file_path -> FileNode chứa các cạnh outgoing
        self._adjacency_out: dict[str, FileNode] = {}
        # adjacency_in: file_path -> FileNode chứa các cạnh incoming
        self._adjacency_in: dict[str, FileNode] = {}
        self._edge_count: int = 0

    # ====== Build phase API (chỉ dùng khi đang build graph) ======

    def clear(self) -> None:
        """
        Xoá toàn bộ dữ liệu trong graph.

        Hàm này phục vụ cho trường hợp muốn reuse instance hiện tại
        thay vì tạo instance mới.
        """

        self._adjacency_out.clear()
        self._adjacency_in.clear()
        self._edge_count = 0

    def add_edge(self, edge: Edge) -> None:
        """
        Thêm một cạnh vào graph.

        Hàm này được gọi trong giai đoạn build graph; sau khi build xong,
        graph nên được xem là immutable đối với callers bên ngoài.
        """

        if not edge.source_file or not edge.target_file:
            return

        source_path = edge.source_file
        target_path = edge.target_file

        source_node = self._adjacency_out.get(source_path)
        if source_node is None:
            source_node = FileNode(file_path=source_path)
            self._adjacency_out[source_path] = source_node

        target_node = self._adjacency_in.get(target_path)
        if target_node is None:
            target_node = FileNode(file_path=target_path)
            self._adjacency_in[target_path] = target_node

        source_node.edges_out.append(edge)
        target_node.edges_in.append(edge)
        self._edge_count += 1

    def add_edges(self, edges: list[Edge]) -> None:
        """
        Thêm nhiều cạnh vào graph một cách hiệu quả.
        """

        for edge in edges:
            self.add_edge(edge)

    # ====== Query API ======

    def get_related_files(
        self,
        file_path: str,
        max_depth: int = 1,
        edge_kinds: Optional[Set[EdgeKind]] = None,
    ) -> set[str]:
        """
        Lấy danh sách file liên quan tới `file_path` bằng BFS.

        Args:
            file_path: Đường dẫn tuyệt đối của file nguồn
            max_depth: Độ sâu tối đa (1 = chỉ hàng xóm trực tiếp)
            edge_kinds: Tập các EdgeKind được phép duyệt; None = tất cả

        Returns:
            Tập đường dẫn file liên quan (không bao gồm chính `file_path`)
        """

        result_with_depth = self.get_related_files_with_depth(
            file_path=file_path,
            max_depth=max_depth,
            edge_kinds=edge_kinds,
        )
        return set(result_with_depth.keys())

    def get_related_files_with_depth(
        self,
        file_path: str,
        max_depth: int = 1,
        edge_kinds: Optional[Set[EdgeKind]] = None,
    ) -> dict[str, int]:
        """
        Tương tự `get_related_files` nhưng trả về độ sâu tới từng file.

        Returns:
            Dict mapping: file_path -> depth (1..max_depth)
        """

        if max_depth < 1:
            return {}

        # Nếu không có edge_kinds được chỉ định, duyệt tất cả các loại cạnh
        allowed_kinds: Optional[Set[EdgeKind]] = (
            set(edge_kinds) if edge_kinds is not None else None
        )

        visited: dict[str, int] = {}
        queue: deque[tuple[str, int]] = deque()

        start_path = file_path
        if start_path not in self._adjacency_out:
            # Nếu file chưa có outgoing edges vẫn có thể có incoming,
            # nhưng từ góc độ "related from", chúng ta coi là không có
            return {}

        queue.append((start_path, 0))
        visited[start_path] = 0

        while queue:
            current_path, current_depth = queue.popleft()

            if current_depth >= max_depth:
                continue

            node = self._adjacency_out.get(current_path)
            if node is None:
                continue

            for edge in node.edges_out:
                if allowed_kinds is not None and edge.kind not in allowed_kinds:
                    continue

                neighbor = edge.target_file
                next_depth = current_depth + 1

                # Nếu đã từng ghé qua neighbor với depth nhỏ hơn thì giữ depth nhỏ hơn
                prev_depth = visited.get(neighbor)
                if prev_depth is None or next_depth < prev_depth:
                    visited[neighbor] = next_depth
                    queue.append((neighbor, next_depth))

        # Loại bỏ file gốc khỏi kết quả
        visited.pop(start_path, None)
        return visited

    def get_edges_from(self, file_path: str) -> list[Edge]:
        """
        Lấy tất cả cạnh đi ra từ một file.
        """

        node = self._adjacency_out.get(file_path)
        if not node:
            return []
        return list(node.edges_out)

    def get_edges_to(self, file_path: str) -> list[Edge]:
        """
        Lấy tất cả cạnh đi vào một file.
        """

        node = self._adjacency_in.get(file_path)
        if not node:
            return []
        return list(node.edges_in)

    def all_files(self) -> set[str]:
        """
        Lấy tập tất cả file đã có mặt trong graph (có edge in hoặc out).
        """

        files: set[str] = set(self._adjacency_out.keys()) | set(
            self._adjacency_in.keys()
        )
        return files

    def file_count(self) -> int:
        """
        Trả về số lượng file hiện có trong graph.
        """

        return len(self.all_files())

    def edge_count(self) -> int:
        """
        Trả về tổng số cạnh trong graph.
        """

        return self._edge_count

    def remove_edges_for_file(self, file_path: str) -> None:
        """
        Xóa tất cả edges (incoming + outgoing) liên quan đến một file.

        Được dùng cho incremental update: trước khi rebuild quan hệ cho
        một file, cần xóa edges cũ để tránh giữ lại dữ liệu stale.
        """

        # Xóa outgoing edges
        source_node = self._adjacency_out.pop(file_path, None)
        if source_node is not None:
            for edge in list(source_node.edges_out):
                target_path = edge.target_file
                target_node = self._adjacency_in.get(target_path)
                if target_node is not None:
                    try:
                        target_node.edges_in.remove(edge)
                    except ValueError:
                        pass
                    if not target_node.edges_in:
                        self._adjacency_in.pop(target_path, None)
                self._edge_count -= 1

        # Xóa incoming edges
        target_node = self._adjacency_in.pop(file_path, None)
        if target_node is not None:
            for edge in list(target_node.edges_in):
                source_path = edge.source_file
                src_node = self._adjacency_out.get(source_path)
                if src_node is not None:
                    try:
                        src_node.edges_out.remove(edge)
                    except ValueError:
                        pass
                    if not src_node.edges_out:
                        self._adjacency_out.pop(source_path, None)
                self._edge_count -= 1
