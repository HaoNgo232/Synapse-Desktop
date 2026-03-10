"""
Session Manager - Quan ly selection (danh sach file dang chon) cho MCP sessions.

Module nay xu ly CRUD operations cho .synapse/selection.json,
bao gom doc, ghi, them, xoa file khoi selection.

Su dung SelectionState v2 lam schema chuan duy nhat, backward-compatible voi v1.
"""

import json
import threading
from pathlib import Path

from domain.selection.provenance import SelectionState
from domain.selection.selection_reader import read_selection_state
from infrastructure.mcp.utils.file_utils import atomic_write

_selection_lock = threading.Lock()


class SessionManager:
    """Quan ly file selection cho build_prompt va cac tool khac.

    Su dung SelectionState v2 (paths + provenance) lam source of truth.
    Backward-compatible: tu dong doc va migrate v1 format.
    """

    @staticmethod
    def get_selection(session_file: Path, workspace: Path) -> str:
        """Doc danh sach file dang duoc chon tu file session.

        Args:
            session_file: Path toi selection.json.
            workspace: Workspace root path.

        Returns:
            String mo ta cac file dang duoc chon.
        """
        state = read_selection_state(session_file)
        if not state.paths:
            return "No selection found. Use action='set' to create one."
        return f"Selected {len(state.paths)} files:\n" + "\n".join(state.paths)

    @staticmethod
    def get_selection_state(session_file: Path) -> SelectionState:
        """Doc SelectionState v2 tu file session.

        Dung cho build_prompt va cac noi can truy cap truc tiep SelectionState.

        Args:
            session_file: Path toi selection.json.

        Returns:
            SelectionState v2 (co the rong neu file chua ton tai).
        """
        return read_selection_state(session_file)

    @staticmethod
    def set_selection(session_file: Path, workspace: Path, paths: list[str]) -> str:
        """Ghi de toan bo danh sach file duoc chon.

        Validate tung path truoc khi ghi de dam bao
        khong co path traversal va file ton tai.
        Luon ghi v2 format.

        Args:
            session_file: Path toi selection.json.
            workspace: Workspace root path.
            paths: Danh sach relative paths can set.

        Returns:
            String ket qua.
        """
        with _selection_lock:
            valid = []
            for rp in paths:
                fp = (workspace / rp).resolve()
                if not fp.is_relative_to(workspace):
                    return f"Error: Path traversal detected for: {rp}"
                if not fp.is_file():
                    return f"Error: File not found: {rp}"
                valid.append(rp)

            state = SelectionState()
            state.add_paths(valid, "user")
            atomic_write(session_file, json.dumps(state.to_dict(), indent=2))
            return f"Selection updated: {len(valid)} files selected."

    @staticmethod
    def add_selection(session_file: Path, workspace: Path, paths: list[str]) -> str:
        """Them file vao danh sach hien tai (bo qua duplicates).

        Doc state hien tai (v1 hoac v2), merge paths moi, ghi lai v2.

        Args:
            session_file: Path toi selection.json.
            workspace: Workspace root path.
            paths: Danh sach relative paths can them.

        Returns:
            String ket qua.
        """
        with _selection_lock:
            state = read_selection_state(session_file)

            added = 0
            for rp in paths:
                fp = (workspace / rp).resolve()
                if not fp.is_relative_to(workspace):
                    return f"Error: Path traversal detected for: {rp}"
                if not fp.is_file():
                    return f"Error: File not found: {rp}"
                if rp not in state.paths:
                    added += 1
                state.add_paths([rp], "user")

            atomic_write(session_file, json.dumps(state.to_dict(), indent=2))
            return f"Added {added} files. Total selection: {len(state.paths)} files."

    @staticmethod
    def clear_selection(session_file: Path) -> str:
        """Xoa toan bo selection.

        Ghi v2 format rong.

        Args:
            session_file: Path toi selection.json.

        Returns:
            String xac nhan da xoa.
        """
        with _selection_lock:
            state = SelectionState()
            atomic_write(session_file, json.dumps(state.to_dict(), indent=2))
            return "Selection cleared."
