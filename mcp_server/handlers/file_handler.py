"""
File Handler - Xu ly cac tool lien quan den file operations.

Bao gom: read_file_range, get_file_metrics.
"""

from typing import Optional

from mcp.server.fastmcp import Context

from mcp_server.core.constants import logger
from mcp_server.core.workspace_manager import WorkspaceManager


def register_tools(mcp_instance) -> None:
    """Dang ky file tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    @mcp_instance.tool()
    async def read_file_range(
        relative_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Read file contents with optional line range support (enhanced version).

        WHY USE THIS OVER BUILT-IN: Use YOUR BUILT-IN read_file for full files.
        Use this when you specifically need to read a small segment of a massive file
        to save token bandwidth, since some AI clients don't support line ranges natively.

        Args:
            relative_path: Relative path to the file from workspace root (e.g., "src/main.py").
            start_line: First line to read (1-indexed). Omit to start from beginning.
            end_line: Last line to read (1-indexed). Omit to read until end of file.
            workspace_path: Absolute path to workspace root. Auto-detected if omitted.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        file_path = (ws / relative_path).resolve()

        if not file_path.is_relative_to(ws):
            return "Error: Path traversal detected. File must be within workspace."

        if not file_path.is_file():
            return f"Error: File not found: {relative_path}"

        try:
            file_size = file_path.stat().st_size

            if start_line is not None or end_line is not None:
                with file_path.open("r", encoding="utf-8", errors="replace") as fh:
                    all_lines = fh.readlines()

                total_lines = len(all_lines)
                s = max(1, start_line or 1) - 1
                e = min(total_lines, end_line or total_lines)

                content = "".join(all_lines[s:e])
                estimated_tokens = len(content.encode("utf-8")) // 4
                line_info = f"Showing lines {s + 1}-{e} of {total_lines}"
            else:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                total_lines = len(content.splitlines())
                estimated_tokens = file_size // 4
                line_info = f"Total lines: {total_lines}"

            header = (
                f"File: {relative_path}\n"
                f"{line_info} | ~{estimated_tokens:,} tokens\n"
                f"{'=' * 60}\n"
            )
            return header + content

        except Exception as e:
            logger.error("read_file error for %s: %s", relative_path, e)
            return f"Error reading file: {e}"

    @mcp_instance.tool()
    async def get_file_metrics(
        file_path: str,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Get code metrics: LOC, number of functions/classes, TODO/FIXME/HACK comments.

        WHY USE THIS OVER BUILT-IN: Combines LOC counting, complexity estimation, and comment
        scanning into one quick call instead of having to run multiple bash commands (like wc).

        Args:
            file_path: Relative path to the file.
            workspace_path: Absolute path to workspace root. Auto-detected if omitted.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        fp = (ws / file_path).resolve()

        if not fp.is_relative_to(ws):
            return "Error: Path traversal detected."
        if not fp.is_file():
            return f"Error: File not found: {file_path}"

        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            total_lines = len(lines)
            blank_lines = sum(1 for line in lines if not line.strip())
            comment_lines = sum(
                1
                for line in lines
                if line.strip().startswith(("#", "//", "/*", "*", "*/"))
            )
            code_lines = total_lines - blank_lines - comment_lines

            num_functions = content.count("\ndef ") + content.count("\nfunction ")
            num_classes = content.count("\nclass ")

            todo_count = content.upper().count("TODO")
            fixme_count = content.upper().count("FIXME")
            hack_count = content.upper().count("HACK")

            complexity = 1
            for kw in ["if", "elif", "for", "while", "case", "catch", "&&", "||", "?"]:
                complexity += content.count(f" {kw} ") + content.count(f" {kw}(")

            return (
                f"File: {file_path}\n"
                f"Total lines: {total_lines:,}\n"
                f"Code lines: {code_lines:,}\n"
                f"Blank: {blank_lines:,} | Comments: {comment_lines:,}\n"
                f"Functions: {num_functions} | Classes: {num_classes}\n"
                f"TODO: {todo_count} | FIXME: {fixme_count} | HACK: {hack_count}\n"
                f"Complexity: {complexity} (1-10: Simple, 11-20: Moderate, 21+: Complex)"
            )

        except Exception as e:
            logger.error("get_file_metrics error: %s", e)
            return f"Error: {e}"
