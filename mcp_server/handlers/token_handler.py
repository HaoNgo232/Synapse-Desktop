"""
Token Handler - Xu ly estimate_tokens tool.

Uoc tinh so luong token cua mot danh sach file dung tokenizer thuc te.
"""

import os
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import Context

from mcp_server.core.constants import logger
from mcp_server.core.workspace_manager import WorkspaceManager


def register_tools(mcp_instance) -> None:
    """Dang ky token tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    @mcp_instance.tool()
    async def estimate_tokens(
        file_paths: List[str],
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Estimate token count for a set of files using the actual tokenizer. Essential for managing context window budgets."""
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        abs_paths: list[Path] = []
        for rp in file_paths:
            fp = (ws / rp).resolve()
            if not fp.is_relative_to(ws):
                return f"Error: Path traversal detected for: {rp}"
            if not fp.is_file():
                return f"Error: File not found: {rp}"
            abs_paths.append(fp)

        if not abs_paths:
            return "Error: No valid files provided."

        try:
            from core.tokenization.cancellation import (
                start_token_counting,
                stop_token_counting,
            )
            from services.tokenization_service import TokenizationService

            start_token_counting()
            try:
                service = TokenizationService()
                results = service.count_tokens_batch_parallel(
                    abs_paths, max_workers=4, update_cache=True
                )

                total = sum(results.values())
                breakdown = []
                for fp in abs_paths:
                    count = results.get(str(fp), 0)
                    rel = os.path.relpath(fp, ws)
                    breakdown.append(f"  {rel}: {count:,} tokens")

                return (
                    f"Total: {total:,} tokens\nFiles: {len(abs_paths)}\n\n"
                    + "\n".join(breakdown)
                )
            finally:
                stop_token_counting()
        except Exception as e:
            logger.error("estimate_tokens error: %s", e)
            return f"Error: {e}"
