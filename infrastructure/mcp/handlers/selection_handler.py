"""
Selection Handler - Xu ly manage_selection tool.

Quan ly danh sach file duoc chon (ticked) trong Synapse session.
Supports v2 format with provenance tracking (backward compatible with v1 list format).
"""

import asyncio
import json
import fcntl
from pathlib import Path
from typing import Annotated, List, Optional, Callable

from mcp.server.fastmcp import Context
from pydantic import Field

from domain.selection.provenance import SelectionSource, SelectionState, VALID_SOURCES
from infrastructure.mcp.core.constants import logger
from infrastructure.mcp.core.workspace_manager import WorkspaceManager


def _locked_read_modify_write(
    session_file: Path, modifier_fn: Callable[[SelectionState], SelectionState]
) -> SelectionState:
    """Read the selection JSON, pass it to modifier_fn, write back, all under cross-process lock."""
    # Ensure file exists so we can open it in r+
    if not session_file.exists():
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(SelectionState().to_dict()))

    with open(session_file, "r+", encoding="utf-8") as f:
        # Cross-process exclusive lock
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            try:
                data = json.load(f)
                # Backward compat: v1 format wraps list in {"selected_files": [...]}
                if isinstance(data, dict) and "selected_files" in data and "version" not in data:
                    state = SelectionState.from_dict(data["selected_files"])
                else:
                    state = SelectionState.from_dict(data)
            except (json.JSONDecodeError, OSError):
                state = SelectionState()

            new_state = modifier_fn(state)

            # Always write v2 format
            f.seek(0)
            json.dump(new_state.to_dict(), f, indent=2)
            f.write("\n")
            f.truncate()

            return new_state
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def register_tools(mcp_instance) -> None:
    """Dang ky selection tools voi MCP server."""

    @mcp_instance.tool()
    async def manage_selection(
        action: Annotated[
            str,
            Field(
                description='Action to perform: "get" (list current selection), "set" (replace selection), "add" (append to selection), "clear" (remove all), "get_provenance" (return provenance map).'
            ),
        ] = "get",
        paths: Annotated[
            Optional[List[str]],
            Field(
                description='List of relative file paths for "set" and "add" actions (e.g., ["src/main.py", "src/utils.py"]).'
            ),
        ] = None,
        source: Annotated[
            Optional[str],
            Field(
                description='Provenance source for "set" and "add" actions: "user", "agent", "dependency", "review". Defaults to "agent".'
            ),
        ] = None,
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Manage the list of currently selected (ticked) files in the Synapse session.

        Use this to track files across multiple exploration steps, then pass them to build_prompt with use_selection=True.
        Thread-safe with cross-process file locking.
        Supports provenance tracking (v2 format) with backward compatibility for v1 format.
        """
        effective_source: SelectionSource = "agent"
        if source is not None:
            if source not in VALID_SOURCES:
                return f"Error: Invalid source '{source}'. Use: user, agent, dependency, or review."
            # source is validated to be a valid SelectionSource literal above
            effective_source = source  # type: ignore[assignment]

        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        session_file = WorkspaceManager.get_session_file(ws)

        if action == "get":
            state = SelectionState()
            if session_file.exists():
                try:
                    raw_text = await asyncio.to_thread(
                        session_file.read_text, encoding="utf-8"
                    )
                    data = json.loads(raw_text)
                    # Backward compat: v1 format wraps list in {"selected_files": [...]}
                    if isinstance(data, dict) and "selected_files" in data and "version" not in data:
                        state = SelectionState.from_dict(data["selected_files"])
                    else:
                        state = SelectionState.from_dict(data)
                except (OSError, json.JSONDecodeError) as e:
                    logger.warning("Failed to load selection: %s", e)

            if not state.paths:
                return "No files currently selected."
            return f"Selected files ({len(state.paths)}):\n" + "\n".join(
                f"  {p}" for p in state.paths
            )

        elif action == "get_provenance":
            state = SelectionState()
            if session_file.exists():
                try:
                    raw_text = await asyncio.to_thread(
                        session_file.read_text, encoding="utf-8"
                    )
                    data = json.loads(raw_text)
                    if isinstance(data, dict) and "selected_files" in data and "version" not in data:
                        state = SelectionState.from_dict(data["selected_files"])
                    else:
                        state = SelectionState.from_dict(data)
                except (OSError, json.JSONDecodeError) as e:
                    logger.warning("Failed to load selection provenance: %s", e)

            if not state.provenance:
                return "No provenance data available."
            return json.dumps(state.provenance, indent=2)

        elif action == "clear":

            def clear_modifier(_: SelectionState) -> SelectionState:
                return SelectionState()

            await asyncio.to_thread(
                _locked_read_modify_write, session_file, clear_modifier
            )
            return "Selection cleared."

        elif action in ("set", "add"):
            if not paths:
                return f"Error: 'paths' parameter required for action '{action}'."

            # Validate paths
            for rp in paths:
                fp = (ws / rp).resolve()
                if not fp.is_relative_to(ws):
                    return f"Error: Path traversal detected for: {rp}"
                if not fp.is_file():
                    return f"Error: File not found: {rp}"

            if action == "set":
                src = effective_source

                def set_modifier(_: SelectionState) -> SelectionState:
                    new_state = SelectionState()
                    safe_paths = paths if paths is not None else []
                    new_state.add_paths(safe_paths, src)
                    return new_state

                new_state = await asyncio.to_thread(
                    _locked_read_modify_write, session_file, set_modifier
                )
            else:  # add
                src = effective_source

                def add_modifier(current: SelectionState) -> SelectionState:
                    safe_paths = paths if paths is not None else []
                    current.add_paths(safe_paths, src)
                    return current

                new_state = await asyncio.to_thread(
                    _locked_read_modify_write, session_file, add_modifier
                )

            return f"Selection updated: {len(new_state.paths)} files selected."

        else:
            return f"Error: Invalid action '{action}'. Use: get, set, add, clear, or get_provenance."
