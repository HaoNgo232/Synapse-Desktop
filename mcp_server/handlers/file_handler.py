"""
File Handler - Xu ly cac tool lien quan den file operations.

Bao gom: get_file_metrics. (read_file_range da go bo - dung built-in read_file voi offset/limit.)
"""

from typing import Annotated, Optional

from mcp.server.fastmcp import Context
from pydantic import Field

from mcp_server.core.constants import logger
from mcp_server.core.workspace_manager import WorkspaceManager


def register_tools(mcp_instance) -> None:
    """Dang ky file tools voi MCP server."""

    @mcp_instance.tool()
    async def get_file_metrics(
        file_path: Annotated[
            str,
            Field(
                description="Relative path to the file from workspace root (e.g., 'src/main.py')."
            ),
        ],
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to workspace root. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Get code metrics for a file: lines of code, function/class counts, comments, TODO/FIXME/HACK counts, and cyclomatic complexity estimate.

        Useful for assessing code quality and complexity before refactoring.
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
