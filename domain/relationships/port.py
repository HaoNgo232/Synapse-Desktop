from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable
from domain.relationships.graph import RelationshipGraph

"""
Port interface cho RelationshipGraph theo nguyên tắc Dependency Inversion.

Domain layer chỉ định nghĩa Protocol, không phụ thuộc vào implementation
chi tiết ở application layer (GraphService, caching, threading, v.v.).
"""


@runtime_checkable
class IRelationshipGraphProvider(Protocol):
    """
    Giao diện cung cấp access tới RelationshipGraph đã được build.

    Ý tưởng:
    - Application layer implement interface này (ví dụ: GraphService)
    - Presentation / MCP server chỉ làm việc với Protocol để dễ test và
      tránh phụ thuộc cụ thể vào implementation.
    """

    def get_graph(self) -> RelationshipGraph | None:
        """
        Trả về graph hiện tại nếu đã build, hoặc None nếu chưa sẵn sàng.

        Caller có thể fallback sang cơ chế cũ (DependencyResolver) khi
        nhận None để đảm bảo trải nghiệm người dùng không bị chặn.
        """

        ...

    def ensure_built(self, workspace_root: Path) -> RelationshipGraph:
        """
        Đảm bảo graph đã được build cho workspace tương ứng.

        Implementation có thể block cho tới khi build xong; phù hợp với
        các luồng synchronous như MCP server, background jobs, v.v.
        """

        ...

    def invalidate(self) -> None:
        """
        Đánh dấu graph hiện tại là stale để lần build tiếp theo tạo lại.

        Thường được gọi khi workspace thay đổi cấu trúc lớn hoặc khi
        cần full rebuild thay vì incremental update.
        """

        ...

    def on_workspace_changed(self, workspace_root: Path) -> None:
        """
        Gọi khi user đổi workspace.

        Trigger full graph build trên background thread.
        """
        ...

    def on_files_changed(self, changed_files: list[str]) -> None:
        """
        Gọi khi file watcher detect changes.

        Incremental rebuild chỉ cho affected files.
        """
        ...

    def on_files_deleted(self, deleted_files: list[str]) -> None:
        """
        Gọi khi files bị xóa.

        Remove stale edges khỏi graph.
        """
        ...
