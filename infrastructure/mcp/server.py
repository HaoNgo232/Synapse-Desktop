"""
Synapse MCP Server - Cung cap cac tools cho AI clients (Cursor, Copilot, Antigravity).

Chay qua stdio transport, khong can UI. Su dung lai logic co san cua Synapse
de AI co the kham pha, doc, phan tich va build prompt tu workspace.

Cach chay:
    python main_window.py --run-mcp /path/to/workspace
    # Hoac voi AppImage:
    ./Synapse.AppImage --run-mcp /path/to/workspace

Architecture:
    server.py la lightweight entry point. Logic duoc tach ra:
    - infrastructure/mcp/core/     : constants, workspace_manager, session_manager, profile_resolver
    - infrastructure/mcp/handlers/ : workspace, file, selection, token, analysis, structure,
                                     dependency, git, context, workflow handlers
    - infrastructure/mcp/utils/    : logging_utils, file_utils
"""

import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Dam bao project root nam trong sys.path de import duoc cac module cua Synapse
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Khoi tao MCP Server voi ten hien thi cho AI clients
mcp = FastMCP(
    "Synapse Desktop",
    instructions=(
        "Synapse MCP is running in selection-only mode.\n"
        "\n"
        "Available tool:\n"
        "  - manage_selection: manage selected file paths in the current session "
        "(get, set, add, clear, get_provenance).\n"
        "\n"
        "Other tools are intentionally disabled at aggregate registration level."
    ),
)


def _register_all_tools() -> None:
    """Dang ky tat ca tools tu handlers vao MCP server.

    Import handlers package va goi register_all_tools()
    de dang ky tung nhom tools.
    """
    from infrastructure.mcp.handlers import register_all_tools

    register_all_tools(mcp)


def run_mcp_server(workspace_path: Optional[str] = None) -> None:
    """Khoi dong Synapse MCP Server voi stdio transport.

    Args:
        workspace_path: Duong dan workspace mac dinh (optional, AI co the truyen lai
                        khi goi tool).
    """
    from infrastructure.mcp.utils.logging_utils import force_all_logging_to_stderr
    from infrastructure.mcp.core.constants import logger

    # CRITICAL: Redirect TAT CA logging sang stderr TRUOC khi bat ky module nao log.
    # Synapse logging_config.py mac dinh ghi ra stdout, se lam hong stdio transport.
    force_all_logging_to_stderr()

    if workspace_path:
        logger.info("MCP Server starting with workspace: %s", workspace_path)
    else:
        logger.info("MCP Server starting (no default workspace)")

    # Auto-update MCP configs neu dang chay tu AppImage/exe.
    # Duong dan AppImage co the thay doi khi user di chuyen file,
    # nen moi lan khoi dong ta cap nhat lai command trong cac config da cai.
    # Thao tac nay rat nhanh (chi doc + so sanh JSON, chi ghi khi can thiet).
    try:
        from infrastructure.mcp.config_installer import auto_update_installed_configs

        updated = auto_update_installed_configs()
        if updated:
            logger.info("Auto-updated MCP config for: %s", ", ".join(updated))
    except Exception as e:
        # Khong de loi auto-update lam crash MCP server
        logger.warning("MCP config auto-update failed: %s", e)

    # Preload workflow plugins neu da co workspace path.
    # Viec preload giup list_workflow_plugins/run_workflow_plugin hoat dong ngay,
    # khong can cho den luc tool dau tien moi discover.
    if workspace_path:
        try:
            from infrastructure.plugins.workflow_plugin_loader import (
                discover_and_register_workflow_plugins,
            )

            loaded = discover_and_register_workflow_plugins(Path(workspace_path))
            if loaded:
                logger.info("Loaded workflow plugins: %s", ", ".join(loaded))
        except Exception as e:
            logger.warning("Workflow plugin preload failed: %s", e)

    # Dang ky tat ca tools tu handlers
    _register_all_tools()

    # KHONG goi initialize_encoder() o day vi no cham (import tokenizers).
    # Encoder se duoc init lazy khi tool dau tien can dem token.
    # Dieu quan trong nhat la goi mcp.run() NGAY LAP TUC de kip handshake
    # voi AI client, tranh timeout "context deadline exceeded".
    mcp.run(transport="stdio")


if __name__ == "__main__":
    ws = sys.argv[1] if len(sys.argv) > 1 else None
    run_mcp_server(ws)
