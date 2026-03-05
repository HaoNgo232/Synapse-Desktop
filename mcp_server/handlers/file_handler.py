"""
File Handler - Xu ly cac tool lien quan den file operations.

Bao gom: read_file_range, get_file_metrics.
"""

from typing import Annotated, Optional

from mcp.server.fastmcp import Context
from pydantic import Field

from mcp_server.core.constants import logger
from mcp_server.core.workspace_manager import WorkspaceManager


def register_tools(mcp_instance) -> None:
    """Dang ky file tools voi MCP server."""

    @mcp_instance.tool()
    async def read_file_range(
        relative_path: Annotated[
            str,
            Field(
                description="Relative path to the file from workspace root (e.g., 'src/main.py')."
            ),
        ],
        start_line: Annotated[
            Optional[int],
            Field(
                description="Start line number (1-indexed). Omit to read from beginning."
            ),
        ] = None,
        end_line: Annotated[
            Optional[int],
            Field(
                description="End line number (1-indexed, inclusive). Omit to read to end."
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
        """Read file contents with optional line range support.

        Returns file content with a header showing line info and estimated token count.
        Prefer your built-in read_file if available; use this for large files where you need a specific line range.
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
