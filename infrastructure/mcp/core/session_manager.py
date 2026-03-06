"""
Session Manager - Quan ly selection (danh sach file dang chon) cho MCP sessions.

Module nay xu ly CRUD operations cho .synapse/selection.json,
bao gom doc, ghi, them, xoa file khoi selection.
"""

import json
from pathlib import Path

from infrastructure.mcp.utils.file_utils import atomic_write


class SessionManager:
    """Quan ly file selection cho build_prompt va cac tool khac."""

    @staticmethod
    def get_selection(session_file: Path, workspace: Path) -> str:
        """Doc danh sach file dang duoc chon tu file session.

        Args:
            session_file: Path toi selection.json.
            workspace: Workspace root path.

        Returns:
            String mo ta cac file dang duoc chon.
        """
        if not session_file.exists():
            return "No selection found. Use action='set' to create one."
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            selected = data.get("selected_files", [])
            if not selected:
                return "Selection is empty."
            return f"Selected {len(selected)} files:\n" + "\n".join(selected)
        except Exception as e:
            return f"Error reading selection: {e}"

    @staticmethod
    def set_selection(session_file: Path, workspace: Path, paths: list[str]) -> str:
        """Ghi de toan bo danh sach file duoc chon.

        Validate tung path truoc khi ghi de dam bao
        khong co path traversal va file ton tai.

        Args:
            session_file: Path toi selection.json.
            workspace: Workspace root path.
            paths: Danh sach relative paths can set.

        Returns:
            String ket qua.
        """
        valid = []
        for rp in paths:
            fp = (workspace / rp).resolve()
            if not fp.is_relative_to(workspace):
                return f"Error: Path traversal detected for: {rp}"
            if not fp.is_file():
                return f"Error: File not found: {rp}"
            valid.append(rp)

        data = {"selected_files": valid}
        atomic_write(session_file, json.dumps(data, indent=2))
        return f"Selection updated: {len(valid)} files selected."

    @staticmethod
    def add_selection(session_file: Path, workspace: Path, paths: list[str]) -> str:
        """Them file vao danh sach hien tai (bo qua duplicates).

        Args:
            session_file: Path toi selection.json.
            workspace: Workspace root path.
            paths: Danh sach relative paths can them.

        Returns:
            String ket qua.
        """
        existing: list[str] = []
        if session_file.exists():
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                existing = data.get("selected_files", [])
            except Exception:
                pass

        existing_set = set(existing)
        added = 0
        for rp in paths:
            fp = (workspace / rp).resolve()
            if not fp.is_relative_to(workspace):
                return f"Error: Path traversal detected for: {rp}"
            if not fp.is_file():
                return f"Error: File not found: {rp}"
            if rp not in existing_set:
                existing.append(rp)
                existing_set.add(rp)
                added += 1

        data = {"selected_files": existing}
        atomic_write(session_file, json.dumps(data, indent=2))
        return f"Added {added} files. Total selection: {len(existing)} files."

    @staticmethod
    def clear_selection(session_file: Path) -> str:
        """Xoa toan bo selection.

        Args:
            session_file: Path toi selection.json.

        Returns:
            String xac nhan da xoa.
        """
        data = {"selected_files": []}
        atomic_write(session_file, json.dumps(data, indent=2))
        return "Selection cleared."
