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
    - mcp_server/core/     : constants, workspace_manager, session_manager, profile_resolver
    - mcp_server/handlers/ : workspace, file, selection, token, analysis, structure,
                             dependency, git, context, workflow handlers
    - mcp_server/utils/    : logging_utils, file_utils
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
        "Synapse Desktop provides codebase analysis capabilities that go beyond "
        "standard file reading and text search.\n"
        "\n"
        "What Synapse adds to your native tools:\n"
        "  - AST-level code understanding: get_codemap, batch_codemap, get_symbols "
        "extract function/class signatures via Tree-sitter parsing, saving 70-80% tokens "
        "vs reading full files.\n"
        "  - Dependency & impact analysis: get_imports_graph resolves cross-file imports, "
        "get_related_tests maps source files to their test files, blast_radius analyzes change impact.\n"
        "  - Token-aware context packaging: estimate_tokens counts tokens accurately, "
        "build_prompt packages files into structured prompts with optional dependency "
        "expansion and token budget management.\n"
        "  - Project intelligence: explain_architecture generates architecture summaries, "
        "start_session auto-discovers project structure and technical debt.\n"
        "  - Workflow tools: rp_build, rp_review, rp_refactor, rp_investigate, rp_test "
        "automate multi-step analysis workflows with scope detection and token optimization.\n"
        "\n"
        "For basic file reading, directory listing, text search, and command execution, "
        "prefer your native tools — they have lower overhead."
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
