"""
Workspace Manager - Quan ly workspace resolution va validation.

Module nay cung cap cac method de resolve, validate workspace paths
va dam bao workspace la hop le truoc khi thuc hien bat ky operation nao.

Supports auto-detection of workspace path from MCP Context roots
when workspace_path is not explicitly provided.
"""

from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse


class WorkspaceManager:
    """Quan ly workspace resolution va validation cho MCP tools."""

    @staticmethod
    async def resolve(
        workspace_path: Optional[str] = None,
        ctx: Optional[object] = None,
    ) -> Path:
        """Resolve workspace path tu string thanh Path object da validate.

        Logic uu tien:
        1. Neu workspace_path duoc cung cap (explicit) -> su dung no.
        2. Neu khong, thu auto-detect tu MCP Context roots (protocol standard).
        3. Cuoi cung, fallback ve Current Working Directory (CWD) - rat on dinh
           vi MCP clients luon launch process o project root.

        Args:
            workspace_path: Duong dan workspace dang string (optional).
            ctx: MCP Context object (optional, dung cho auto-detect).

        Returns:
            Path object da resolve.

        Raises:
            ValueError: Khi workspace khong ton tai, khong phai thu muc,
                        hoac khong the detect duoc.
        """
        ws_str = workspace_path

        # Auto-detect from MCP Context roots if workspace_path not provided
        if not ws_str and ctx is not None:
            ws_str = await WorkspaceManager._detect_from_context(ctx)

        # Ultimate fallback: Use Current Working Directory
        if not ws_str:
            ws_str = str(Path.cwd())

        ws = Path(ws_str).resolve()

        if not ws.exists():
            raise ValueError(
                f"Workspace does not exist: {ws}. "
                f"You must provide the valid absolute path to the root "
                f"directory of the target project you are working on."
            )
        if not ws.is_dir():
            raise ValueError(
                f"Workspace is not a directory: {ws}. "
                f"The workspace_path must be a directory, not a file."
            )

        return ws

    @staticmethod
    async def _detect_from_context(ctx: object) -> Optional[str]:
        """Try to extract workspace path from MCP Context roots.

        MCP clients (e.g., Claude Desktop, Cursor) can expose workspace
        roots via ctx.session.list_roots(). Each root has a `uri` field
        in file:// format.

        Args:
            ctx: MCP Context object.

        Returns:
            Workspace path string or None if detection fails.
        """
        try:
            # FastMCP injects Context which has session.list_roots()
            session = getattr(ctx, "session", None)
            if session is None:
                return None

            list_roots_fn = getattr(session, "list_roots", None)
            if list_roots_fn is None:
                return None

            roots_result = await list_roots_fn()
            if roots_result is None:
                return None

            # roots_result may be a ListRootsResult with .roots attribute,
            # or it may be a list directly
            roots = getattr(roots_result, "roots", roots_result)
            if not roots:
                return None

            # Use the first root
            first_root = roots[0]

            # Extract URI - could be a Root object with .uri or a dict
            uri = None
            if hasattr(first_root, "uri"):
                uri = first_root.uri
            elif isinstance(first_root, dict):
                uri = first_root.get("uri")

            if not uri:
                return None

            # Parse file:// URI to filesystem path
            return WorkspaceManager._uri_to_path(uri)

        except Exception:
            # Auto-detection is best-effort; never crash
            return None

    @staticmethod
    def _uri_to_path(uri: str) -> Optional[str]:
        """Convert a file:// URI to a filesystem path.

        Args:
            uri: URI string (e.g., "file:///home/user/project").

        Returns:
            Filesystem path string or None if not a file:// URI.
        """
        if not uri:
            return None

        parsed = urlparse(uri)
        if parsed.scheme != "file":
            return None

        # On Unix, path is parsed.path (e.g., /home/user/project)
        # On Windows, path may be /C:/Users/... -> strip leading /
        path = unquote(parsed.path)
        if not path:
            return None

        # Handle Windows paths: /C:/Users/... -> C:/Users/...
        if len(path) >= 3 and path[0] == "/" and path[2] == ":":
            path = path[1:]

        return path

    @staticmethod
    def resolve_sync(workspace_path: str) -> Path:
        """Synchronous resolve for backward compatibility (no auto-detect).

        Args:
            workspace_path: Duong dan workspace dang string.

        Returns:
            Path object da resolve.

        Raises:
            ValueError: Khi workspace khong ton tai hoac khong phai thu muc.
        """
        ws = Path(workspace_path).resolve()

        if not ws.exists():
            raise ValueError(
                f"Workspace does not exist: {ws}. "
                f"You must provide the valid absolute path to the root "
                f"directory of the target project you are working on."
            )
        if not ws.is_dir():
            raise ValueError(
                f"Workspace is not a directory: {ws}. "
                f"The workspace_path must be a directory, not a file."
            )

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
