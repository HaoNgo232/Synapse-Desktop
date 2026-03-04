"""
Workspace Manager - Quan ly workspace resolution va validation.

Module nay cung cap cac method de resolve, validate workspace paths
va dam bao workspace la hop le truoc khi thuc hien bat ky operation nao.
"""

from pathlib import Path


class WorkspaceManager:
    """Quan ly workspace resolution va validation cho MCP tools."""

    @staticmethod
    def resolve(workspace_path: str) -> Path:
        """Resolve workspace path tu string thanh Path object da validate.

        Kiem tra workspace ton tai va la thu muc hop le.

        Args:
            workspace_path: Duong dan workspace dang string.

        Returns:
            Path object da resolve.

        Raises:
            ValueError: Khi workspace khong ton tai hoac khong phai thu muc.
        """
        ws = Path(workspace_path).resolve()

        if not ws.exists():
            raise ValueError(f"Workspace does not exist: {ws}")
        if not ws.is_dir():
            raise ValueError(f"Workspace is not a directory: {ws}")

        return ws

    @staticmethod
    def validate_relative_path(workspace: Path, relative_path: str) -> Path:
        """Validate relative path nam trong workspace (chong path traversal).

        Args:
            workspace: Workspace root path.
            relative_path: Duong dan tuong doi can validate.

        Returns:
            Absolute Path da resolve.

        Raises:
            ValueError: Khi path nam ngoai workspace (path traversal).
        """
        fp = (workspace / relative_path).resolve()

        if not fp.is_relative_to(workspace):
            raise ValueError(f"Path outside workspace: {relative_path}")

        return fp

    @staticmethod
    def get_session_file(workspace: Path) -> Path:
        """Lay duong dan session file (.synapse/selection.json).

        Tu dong tao thu muc .synapse neu chua ton tai.

        Args:
            workspace: Workspace root path.

        Returns:
            Path toi session file.
        """
        session_file = workspace / ".synapse" / "selection.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        return session_file
